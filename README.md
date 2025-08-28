# dt-sim
A Device Tree compilation and overlay simulation tool that generates human-readable text outputs instead of binary files.

## Why dt-sim ?
When working with the device tree overlays, `fdtoverlay` often fails with cryptic error messages like "failed to apply overlay" without telling you what went or where. dt-sim solves this by:
- Simulating the entire DTS compilation process but outputting readable text files
- Providing detailed error message with exact file locations and suggestions
- Making the black-box compilation process transparent so you can see exactly what happens at each stage

## What does it do ?
TBD

## Commands
TBD

## Example Usage
TBD

## Output format
TBD

## Installation
TBD

## Project Status
🚧 In Development 🚧

- [x] Project design & planning
- [ ] Functions
    - [ ] `dt-sim dtc` - DTS compilation simulation
    - [ ] `dt-sim overlay` - Overlay compilation simulation
    - [ ] `dt-sim fdtoverlay` - Overlay merging simulation
