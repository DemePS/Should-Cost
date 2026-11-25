// Hager Should-Cost Builder — infra for what this app owns, not the App Service itself.
//
// The App Service (plan + site) is provisioned and owned by another team and requested,
// not created, by this repo (docs/deployment.md has the request checklist) — this file
// references it as an `existing` resource and only configures what it needs on top of
// it (a staging slot, app settings, access restrictions) plus the two resources that are
// genuinely this app's own: the storage account backing job state, and Application
// Insights. No Key Vault (secrets are App Service application settings injected by
// cd.yml from Azure DevOps variable groups — see docs/deployment.md).
//
// Deploy with pipelines/infra.yml (what-if first, then this). Never creates an App
// Service Plan, an App Service, or an Azure Container Registry — those are placeholders
// resolved from pipelines/variables.yml, referenced here as `existing` or passed in by
// name for the pipeline's own `az` calls (ACR is not referenced in this file at all —
// cd.yml pushes to it directly by name).

@description('Name of the existing App Service (Linux, container) this app deploys onto. Provisioned by the platform team — see docs/deployment.md\'s request checklist. NOT created here.')
param appServiceName string

@description('Resource group the existing App Service lives in, if different from this deployment\'s own resource group.')
param appServiceResourceGroup string = resourceGroup().name

@description('Environment name: dev, test, or prod — used to suffix resource names.')
@allowed(['dev', 'test', 'prod'])
param environmentName string

@description('Azure region for the resources this file creates (storage account, Application Insights).')
param location string = resourceGroup().location

@description('Hager network IP ranges allowed to reach the App Service — see docs/deployment.md. The App Service must not be publicly reachable (no sign-in in v1).')
param allowedIpRanges array

@description('Job retention days, mirrors JOB_RETENTION_DAYS app setting.')
param jobRetentionDays int = 90

var namePrefix = 'shouldcost${environmentName}'
var storageAccountName = toLower(replace('${namePrefix}state', '-', ''))

resource existingAppService 'Microsoft.Web/sites@2023-12-01' existing = {
  name: appServiceName
  scope: resourceGroup(appServiceResourceGroup)
}

resource stagingSlot 'Microsoft.Web/sites/slots@2023-12-01' = {
  parent: existingAppService
  name: 'staging'
  location: location
  properties: {
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: existingAppService.properties.siteConfig.linuxFxVersion
      ipSecurityRestrictions: [
        for range in allowedIpRanges: {
          ipAddress: range
          action: 'Allow'
          priority: 100
          name: 'hager-network'
        }
      ]
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-appi'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

resource jobsTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  name: '${storageAccount.name}/default/shouldcostjobs'
}

resource jobsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/should-cost-jobs'
  properties: {
    publicAccess: 'None'
  }
}

// Storage data-plane roles for the App Service's system-assigned identity — managed
// identity only, no connection strings (should_cost/state/store.py).
var storageTableDataContributorRoleId = '0a9a7e1f-b9d0-4cc4-a60d-0cf2b70cf01f'
var storageBlobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource tableRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, existingAppService.id, storageTableDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageTableDataContributorRoleId)
    principalId: existingAppService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource blobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, existingAppService.id, storageBlobDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
    principalId: existingAppService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// NOTE: a system-assigned identity's client id (AZURE_CLIENT_ID, only needed for the
// optional ManagedIdentityCredential(client_id=...) disambiguation on a resource with
// multiple identities — see should_cost/graph/credentials.py) is NOT exposed as an ARM
// resource property, including on an `existing` reference — only principalId and
// tenantId are. Fetch it separately once this deploys, e.g.
// `az webapp identity show --name <appServiceName> --resource-group <rg> --query clientId`
// — documented in docs/deployment.md, not output here, since Bicep cannot produce it.

@description('The App Service\'s system-assigned managed identity principal id — IT needs this for the SharePoint Sites.Selected grant (docs/sharepoint-access.md) and for the Azure AI Foundry role assignment.')
output managedIdentityPrincipalId string = existingAppService.identity.principalId

output storageAccountName string = storageAccount.name
output applicationInsightsConnectionString string = appInsights.properties.ConnectionString
