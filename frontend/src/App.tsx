import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./auth/AuthProvider";
import { NewAnalysisPage } from "./pages/NewAnalysisPage";
import { JobDetailPage } from "./pages/JobDetailPage";

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<NewAnalysisPage />} />
          <Route path="/jobs/:jobId" element={<JobDetailPage />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
