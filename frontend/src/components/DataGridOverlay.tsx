export function DataGridOverlay() {
  return (
    <>
      <div aria-hidden className="hud-grid fixed inset-0 z-0" />
      <div aria-hidden className="hud-vignette fixed inset-0 z-0" />
      <div aria-hidden className="scanline fixed inset-0 z-0" />
    </>
  );
}
