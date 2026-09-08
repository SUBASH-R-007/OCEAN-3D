# Colorbar, variable and layer controls

Verified locally on 8 September 2026. The Explorer implements the requested controls with the existing React and VTK.js/WebGL 2 stack. No new dependencies or backend changes were required.

| Control | Behavior |
| --- | --- |
| Variable selector | Uses the selected dataset's catalog, including registered variables. Switching variables updates the unit, default range and isovalue, and resets to linear scale. Only available variables are offered. |
| Palette | Thermal, Viridis, Ice and Balance. One shared color mapping drives the selected scalar field, sections, isosurface color and numerical color legend. |
| Minimum and maximum | Edit both limits, then Apply range or press Enter. Blank, reversed, equal and nonfinite limits are rejected inline without changing the applied scale. Scientific notation is supported. |
| Fit / reset | Fit current frame uses finite display samples, or only positive samples in log mode. Constant fields receive a small range around their value. Reset variable range restores catalog limits and linear mode. Fitting is explicit: advancing time does not silently change limits. |
| Linear / log | Five labeled ticks represent equal color intervals. Logarithmic positions use geometric intervals. The range must have a positive minimum; zero and negative samples are hidden and counted. |
| Field opacity | 0–100%, shared by the active volume, horizontal slice, intersecting sections or isosurface. The previous minimum opacity floors on sections and isosurfaces are removed. Zero hides the scalar field. Volume alpha accumulates along the viewing ray, so its apparent opacity is not identical to a flat surface. |
| Overlay opacity | Independent 0–100% controls for instrument tracks/markers, current vectors, and streamlines/particles. Controls appear with the corresponding enabled layer. Zero-opacity instrument labels are hidden from pointer/keyboard interaction. |
| Vertical exaggeration | 1–600×, applied consistently to model geometry and colocated overlays. Geographic positions, scientific depth labels and exported native data are unchanged. |
| Saved/shared view | Palette, range, scale, layer opacities, selected variable and exaggeration are serialized with the view. Older saved views receive the new opacity defaults; invalid settings are bounded on restoration. |

The scalar legend labels the selected variable. Current arrows retain their separate horizontal-speed legend (0–2 m/s with endpoint clipping); signed u/v colors must not be mistaken for speed. Opacity and lighting affect the appearance of the composited 3D image. The 2D analysis chart retains full visibility so it remains readable when the 3D layer is hidden.

## Rendering and scientific consistency

`web/lib/colorScale.ts` owns palettes, validation, tick values, display encoding and GPU transfer knots. In log mode, only the display copy of scalar values is transformed to log10 before GPU lookup. This avoids sampling many logarithmic decades through a linearly spaced lookup texture. Missing and nonpositive values use a transparent sentinel. Native arrays remain unchanged for interpolation, isosurface extraction, comparisons and exports.

Vertical section faces are emitted only when their corners are supported and, in log mode, positive. Unsupported faces remain open. Nonpositive isovalues are explicitly hidden in log mode; the UI explains how to recover. Isovalue navigation follows the actual field range independently of the color limits.

Display scalars use float32, nearest sampling for volume/horizontal slices, and vertex interpolation on section meshes. This is a numerical visualization, not a replacement for native-resolution values. The rendering changes do not establish operational forecast accuracy or universal GPU/browser compatibility.

## Verification

- 34 frontend scientific tests passed, including six new regression cases for logarithmic tick/color agreement, transparent masking, native-array preservation, palette knots, invalid range drafts, and saved opacity/scale bounds.
- TypeScript, authored-code lint, portable Vite build and Vinext/Worker production build passed. Existing large-chunk and future Vite JSON-import warnings remain.
- Browser review exercised all four palettes, temperature/salinity/chlorophyll/current selection, linear and log scales, fit/reset, blank/inverted/nonpositive limits, scientific notation, and fixed limits across time changes.
- Visually checked full versus zero field opacity in sections, volume and isosurface views; independent overlay controls accept 0–100%. A 1% isosurface setting is retained without the old 15% floor. Logarithmic signed-current sections mask negative cells; a nonpositive isovalue shows explanatory feedback.
- Verified 1× and 600× exaggeration, keyboard sliders, and saved-view reload. In the standalone production build, independently set field/instrument/vector/streamline opacity values 11/69/89/43% and 401× exaggeration survived reload.
- Real INCOIS data were checked through the API-connected preview; real HYCOM currents were checked in the standalone Worker preview. Both final browser warning/error logs were empty.
- Phone viewport 390×844: available content width and document scroll width were both 375 px, with one scene canvas. The range editor, wrapped actions and validation feedback were inspected. The temporary viewport override was reset.

Updated local previews are on ports 3000 (scientific API connected) and 3001 (bundled production snapshot). Public publication remains pending the earlier external-upload approval; no source or dataset upload was made during this update.
