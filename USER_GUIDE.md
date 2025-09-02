# dt-sim User Guide

**dt-sim** is a comprehensive Device Tree simulation tool that mimics the behavior of standard Linux device tree tools like `dtc` and `fdtoverlay`. It compiles Device Tree Source (DTS) files into human-readable DTB text format and supports advanced features like node references and overlays.

## 📋 Table of Contents

- [Quick Reference](#quick-reference)
- [Installation](#installation) 
- [Quick Start](#quick-start)
- [Commands Overview](#commands-overview)
- [dt-sim dtc Command](#dt-sim-dtc-command)
- [dt-sim fdtoverlay Command](#dt-sim-fdtoverlay-command)
- [Validation Features](#validation-features)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

## ⚡ Quick Reference

### Most Common Commands

```bash
# Complete workflow (3 steps)
python dt-sim.py dtc base.dts -o base.dtb.txt --validate -v -I include/
python dt-sim.py dtc overlay.dts -o overlay.dtbo.txt --validate -v -I include/
python dt-sim.py fdtoverlay base.dtb.txt overlay.dtbo.txt -o final.dtb.txt --verbose

# Single overlay merge
python dt-sim.py fdtoverlay base.dtb.txt overlay.dtbo.txt -o final.dtb.txt --verbose --show-changes

# Multiple overlay merge
python dt-sim.py fdtoverlay base.dtb.txt wifi.dtbo.txt display.dtbo.txt -o final.dtb.txt --verbose --show-merge

# Production build (clean output)
python dt-sim.py dtc production.dts -o output/prod.dtb.txt --validate --no-warnings
```

### Command Syntax

**dt-sim dtc:**
```
python dt-sim.py dtc [OPTIONS] input.dts -o output.dtb.txt

Required:
  input.dts              Input DTS file
  -o, --output FILE      Output DTB/DTBO text file (.dtb.txt or .dtbo.txt)

Options:
  -v, --verbose          Detailed output
  --validate            Auto-validate after compilation
  --test-overlays       Test node reference overlays
  --no-warnings         Hide validation warnings
  --show-includes       Show include processing
  --check-only          Syntax check only
  -I, --include PATH    Add include search path (can be used multiple times)
```

**dt-sim fdtoverlay:**
```
python dt-sim.py fdtoverlay [OPTIONS] base.dtb.txt overlay1.dtbo.txt [overlay2.dtbo.txt ...] -o final.dtb.txt

Required:
  base.dtb.txt          Base DTB file (compiled with dtc)
  overlay1.dtbo.txt     One or more overlay DTBO files
  -o, --output FILE     Output merged DTB file

Options:
  -v, --verbose         Detailed merge process
  --show-merge          Display merge summary after completion
  --show-changes        Show merge summary before generating output
  --validate-only       Validate merge without generating output
```

### Real-World Example

```bash
# RK3588 SoC example with overlays
cd dt-sim

# Compile base (108 nodes, 72 phandles)
python dt-sim.py dtc input/complex/rk3588-board.dts -o output/complex/base.dtb.txt --validate -v -I input/include/

# Compile WiFi overlay (SDIO, I2C sensors, SPI flash)
python dt-sim.py dtc input/overlays/enable-wifi.dts -o output/overlays/wifi.dtbo.txt --validate -v -I input/include/

# Compile display overlay (HDMI, touch, backlight)
python dt-sim.py dtc input/overlays/enable-display.dts -o output/overlays/display.dtbo.txt --validate -v -I input/include/

# Merge everything
python dt-sim.py fdtoverlay output/complex/base.dtb.txt output/overlays/wifi.dtbo.txt output/overlays/display.dtbo.txt -o output/final/complete-system.dtb.txt --verbose --show-changes
```

### File Extensions & Workflow

| Stage | Command | Purpose |
|-------|---------|---------|
| **Compile Base** | `dtc base.dts -o base.dtb.txt` | Generate base DTB |
| **Compile Overlay** | `dtc overlay.dts -o overlay.dtbo.txt` | Generate overlay DTBO |
| **Merge** | `fdtoverlay base.dtb.txt overlay.dtbo.txt -o final.dtb.txt` | Combine base + overlay |

### Quick Troubleshooting

| Issue | Quick Fix |
|-------|-----------|
| Include not found | Add `-I include_directory/` |
| Phandle unresolved | Check label definitions in included files |
| Node reference ignored | Ensure `&label` is outside root node `/ { }` |
| Slow compilation | Check for circular includes |

### Pro Tips

- **Always use `--validate`** - catches issues immediately
- **Use `-v` during development** for detailed debugging info  
- **Test node references** with `--test-overlays` when using `&label` syntax
- **Sequential overlays** are applied in command-line order
- **Use .dtbo.txt extension** for overlay compilation output

## 🚀 Installation

1. Clone or download the dt-sim repository
2. Ensure Python 3.7+ is installed
3. No additional dependencies required - uses only Python standard library

```bash
cd dt-sim
python dt-sim.py --help
```

## ⚡ Quick Start

See [Quick Reference](#quick-reference) section above for immediate commands, or follow the workflow:

1. **Compile base**: `dtc base.dts -o base.dtb.txt --validate`
2. **Compile overlays**: `dtc overlay.dts -o overlay.dtbo.txt --validate`  
3. **Merge**: `fdtoverlay base.dtb.txt overlay.dtbo.txt -o final.dtb.txt --verbose`

For detailed examples, see the [Examples](#examples) section below.

## 🛠 Commands Overview

dt-sim supports two main commands:

| Command | Purpose | Output Format |
|---------|---------|---------------|
| `dtc` | Compile DTS to DTB/DTBO text | `.dtb.txt` or `.dtbo.txt` |
| `fdtoverlay` | Merge base DTB + overlay DTBOs | `.dtb.txt` |

**Note:** The `dtc` command handles both regular device trees and overlays - just specify the appropriate output extension.

## 📖 dt-sim dtc Command

The `dtc` command compiles Device Tree Source files into human-readable DTB or DTBO text format. Use `.dtb.txt` for base device trees and `.dtbo.txt` for overlays.

### Syntax
```bash
# Compile base device tree
python dt-sim.py dtc [options] input.dts -o output.dtb.txt

# Compile overlay device tree
python dt-sim.py dtc [options] overlay.dts -o output.dtbo.txt
```

### Required Arguments
- `input.dts` - Input Device Tree Source file
- `-o, --output` - Output DTB text file path

### Options

#### Basic Options
| Option | Description |
|--------|-------------|
| `-v, --verbose` | Show detailed compilation process |
| `--show-includes` | Display include file processing |
| `--check-only` | Validate syntax only, don't generate output |
| `-I, --include PATH` | Add include search path (can be used multiple times) |

#### Validation Options
| Option | Description |
|--------|-------------|
| `--validate` | Automatically validate DTB output after compilation |
| `--test-overlays` | Test node reference overlay functionality |
| `--no-warnings` | Hide warning messages during validation |

### Features Supported

#### ✅ Include Processing
- `#include "file.dtsi"` - Local includes
- `#include <file.dtsi>` - System includes
- Recursive include support
- Multiple include paths via `-I`

#### ✅ Node References & Overlays
- `&label { ... }` syntax for modifying existing nodes
- Property overrides: `&gpio { status = "disabled"; }`
- Property additions: `&uart { current-speed = <115200>; }`
- Child node additions via references

#### ✅ Advanced Features
- Phandle generation and resolution
- Label tracking and mapping
- Source file attribution in output
- Property validation
- Comprehensive error reporting

### Output Format

The generated `.dtb.txt` file includes:
- Source file information and timestamps
- Phandle table with label mappings
- Complete device tree structure with source attribution
- Property values in proper DTS format

Example output structure:
```
/*
 * Generated by dt-sim dtc - mimics compiled DTB
 * Source file: test.dts
 * Total nodes: 7
 * Total phandles: 3
 */

/dts-v1/;

/*
 * ===== PHANDLE TABLE =====
 * phandle_map: {
 *   gpio: 0x01 (/gpio@12380000)
 *   uart0: 0x02 (/uart@12340000)
 * }
 */

/ {
    compatible = "test,board"; /* test.dts:3 */
    
    gpio: gpio@12380000 {
        /* phandle: 0x01 (auto-assigned) */
        compatible = "simple-gpio"; /* base.dtsi:6 */
        status = "disabled"; /* test.dts:12 */
    };
};
```

## 🔧 Complete Device Tree Workflow

dt-sim supports the complete Device Tree toolchain workflow:

### Step 1: Compile Base Device Tree
```bash
python dt-sim.py dtc base.dts -o base.dtb.txt --validate -v
```

### Step 2: Compile Overlay Device Trees
```bash
python dt-sim.py dtc wifi-overlay.dts -o wifi.dtbo.txt --validate -v
python dt-sim.py dtc display-overlay.dts -o display.dtbo.txt --validate -v
```

### Step 3: Merge Base + Overlays
```bash
python dt-sim.py fdtoverlay base.dtb.txt wifi.dtbo.txt display.dtbo.txt -o final.dtb.txt --verbose --show-changes
```

## 🔄 dt-sim fdtoverlay Command

The `fdtoverlay` command merges a base DTB file with one or more overlay DTBO files to create a final merged DTB.

### Syntax
```bash
python dt-sim.py fdtoverlay [options] base.dtb.txt overlay1.dtbo.txt [overlay2.dtbo.txt ...] -o final.dtb.txt
```

### Required Arguments
- `base.dtb.txt` - Base DTB file (compiled with `dtc`)
- `overlay1.dtbo.txt` - One or more overlay DTBO files
- `-o, --output` - Output merged DTB file path

### Options
| Option | Description |
|--------|-------------|
| `-v, --verbose` | Show detailed merge process |
| `--show-merge` | Display merge summary after completion |
| `--show-changes` | Show merge summary before generating output |
| `--validate-only` | Validate merge process without generating output file |

### Features
- ✅ **Multi-overlay support** - Merge multiple overlay files in sequence
- ✅ **Phandle merging** - Combines phandle tables from base and overlays  
- ✅ **Label preservation** - Maintains all label mappings
- ✅ **Change tracking** - Records all applied modifications
- ✅ **Metadata generation** - Includes merge timestamps and statistics

### Output Format
The merged DTB includes:
- Complete merge metadata (source files, timestamps, statistics)
- Combined phandle table from base and all overlays
- Original base DTB content
- Record of all applied overlay changes

Example merged output header:
```
/*
 * Generated by dt-sim fdtoverlay - merged DTB
 * Base file: input/base.dts
 * Overlay files:
 *   - input/wifi-overlay.dts
 *   - input/display-overlay.dts
 * Merge timestamp: 2025-09-02 14:57:53
 * Base nodes: 108
 * Base phandles: 72
 * Overlays applied: 2
 */
```

## ✅ Validation Features

dt-sim includes comprehensive validation capabilities:

### Automatic Validation
When using `--validate`, the tool automatically checks:

#### Structure Validation
- ✅ DTS version declaration (`/dts-v1/;`)
- ✅ Root node existence and properties
- ✅ Recommended properties (`#address-cells`, `#size-cells`)
- ✅ Node count and structure

#### Reference Validation  
- ✅ Phandle reference resolution (`&label`)
- ✅ Label mappings and assignments
- ✅ Unresolved references detection
- ✅ Unused phandle identification

#### Property Validation
- ✅ Property format validation (`compatible`, `status`, `reg`)
- ✅ Empty property detection
- ✅ Value format checking
- ✅ Numeric value validation (hex/decimal)

#### Overlay Validation (`--test-overlays`)
- ✅ Node reference functionality (`&gpio { ... }`)
- ✅ Property override verification
- ✅ Property addition confirmation
- ✅ Child node addition via references
- ✅ Expected vs actual value comparison

### Validation Methods
dt-sim provides validation during compilation and merging:

```bash
# Validation during compilation
python dt-sim.py dtc input.dts -o output.dtb.txt --validate --test-overlays -v

# Validation during merging
python dt-sim.py fdtoverlay base.dtb.txt overlay.dtbo.txt -o final.dtb.txt --validate-only --show-changes

# Re-compile with validation to check existing files
python dt-sim.py dtc original-source.dts -o revalidated.dtb.txt --validate --test-overlays -v
```

## 📚 Examples

### Basic Compilation
```bash
# Compile base device tree
python dt-sim.py dtc device.dts -o output/device.dtb.txt

# Compile overlay device tree
python dt-sim.py dtc overlay.dts -o output/overlay.dtbo.txt

# With verbose output and validation
python dt-sim.py dtc device.dts -o output/device.dtb.txt --validate -v
```

### Advanced Features
```bash
# Multiple include paths for complex projects
python dt-sim.py dtc board.dts -o output/board.dtb.txt -I include/ -I ../common/ -v

# Test node references and overlays
python dt-sim.py dtc test_overlay.dts -o output/test.dtb.txt --validate --test-overlays -v

# Merge validation only (test without generating output)
python dt-sim.py fdtoverlay base.dtb.txt overlay.dtbo.txt -o /dev/null --validate-only --show-changes

# Syntax validation only (no compilation)
python dt-sim.py dtc large-file.dts -o output/check.dtb.txt --check-only -v
```

### Node Reference Examples

#### Input DTS with References
```dts
/dts-v1/;

#include "base.dtsi"

// Node references - modify existing nodes
&gpio {
    status = "disabled";        // Override property
    pinctrl-names = "default";  // Add new property
};

&i2c0 {
    clock-frequency = <100000>;
    
    // Add child nodes via reference
    eeprom@50 {
        compatible = "atmel,24c02";
        reg = <0x50>;
    };
};
```

#### Compilation Command
```bash
python dt-sim.py dtc overlay_test.dts -o output/overlay_test.dtb.txt --validate --test-overlays -v
```

#### Expected Validation Output
```
[OK] DTB validation PASSED
[OK] All overlay tests PASSED - Node references working correctly!
[OK] Property 'status' in /gpio@12380000 correctly set to 'disabled'
[OK] Property 'pinctrl-names' in /gpio@12380000 correctly set to 'default'
[OK] Property 'compatible' in /i2c@12360000/eeprom@50 correctly set to 'atmel,24c02'
```

### Troubleshooting Compilation
```bash
# Check syntax only
python dt-sim.py dtc problematic.dts -o output/test.dtb.txt --check-only -v

# Show include processing
python dt-sim.py dtc complex.dts -o output/complex.dtb.txt --show-includes -v

# Re-validate by recompiling
python dt-sim.py dtc original-suspicious.dts -o revalidated.dtb.txt --validate --test-overlays -v
```

## 🔍 Troubleshooting

### Common Issues

#### Include File Not Found
```
ERROR: Cannot resolve include: missing.dtsi
```
**Solution:** Use `-I` to add include paths:
```bash
python dt-sim.py dtc file.dts -o output.dtb.txt -I ./include/ -I ../common/
```

#### Phandle Reference Errors
```
[WARN] Unresolved phandle reference: &missing_label
```
**Solution:** Ensure referenced labels are defined in included files or the main DTS.

#### Node Reference Not Working
```
[FAIL] Expected property 'status' not found in /gpio@12380000
```
**Solution:** Check that:
1. The target node has a proper label: `gpio: gpio@12380000 { ... }`
2. The reference syntax is correct: `&gpio { status = "disabled"; }`
3. The reference is outside any root node block

#### Validation Failures
```
[FAIL] DTB validation FAILED - 2 errors
```
**Solution:** 
1. Run with `-v` for detailed error information
2. Check the specific error messages
3. Use `--no-warnings` to focus on critical errors only

### Performance Issues

If compilation is slow (>30 seconds):
1. Check for circular includes
2. Reduce complexity of constant definitions
3. Use `--check-only` first to validate syntax quickly

### Getting Help

```bash
# General help
python dt-sim.py --help

# Command-specific help
python dt-sim.py dtc --help
python dt-sim.py fdtoverlay --help
```

## 📝 Best Practices

### Development Workflow
1. **Always use validation**: `--validate` catches issues early
2. **Use verbose mode**: `-v` during development for debugging
3. **Test overlays**: `--test-overlays` when using node references
4. **Organize includes**: Use `-I` for clean include paths

### Production Usage
1. **Validate clean**: `--validate --no-warnings` for production builds
2. **CI/CD integration**: Use `--validate-only` with fdtoverlay for testing
3. **Version control**: Include both `.dts` source and `.dtb.txt` output

### Node Reference Tips
1. **Label everything**: Add labels to nodes you might reference later
2. **Test thoroughly**: Always use `--test-overlays` when using `&` syntax  
3. **Document references**: Comment why you're overriding properties
4. **Keep it simple**: Avoid complex nested reference structures

---

## 🎯 Summary

dt-sim provides a complete Device Tree development experience with:

- ✅ **Full DTS compilation** with include support
- ✅ **Node reference overlays** (`&label` syntax)  
- ✅ **Complete toolchain workflow** - dtc + fdtoverlay
- ✅ **DTB/DTBO merging** with multi-overlay support
- ✅ **Comprehensive validation** with automatic testing
- ✅ **Detailed error reporting** with source attribution
- ✅ **Production-ready** compilation and merging capabilities
- ✅ **Complex SoC support** - tested with RK3588 device trees

### Complete Command Reference

```bash
# Compile device trees
python dt-sim.py dtc input.dts -o output.dtb.txt [options]

# Merge base + overlays  
python dt-sim.py fdtoverlay base.dtb.txt overlay1.dtbo.txt [overlay2.dtbo.txt ...] -o final.dtb.txt [options]
```

For more examples and advanced usage, check the `input/` and `output/` directories in the repository.
