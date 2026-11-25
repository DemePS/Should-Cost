import "@testing-library/jest-dom/vitest";

// jsdom has no ResizeObserver — recharts' ResponsiveContainer (used by WaterfallChart /
// SensitivityTornado) needs one to even mount.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub;
