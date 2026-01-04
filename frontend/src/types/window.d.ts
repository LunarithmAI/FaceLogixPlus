export interface CaptureFrameWindow extends Window {
  captureFrame?: () => string | null;
}

declare global {
  interface Window {
    captureFrame?: () => string | null;
  }
}
