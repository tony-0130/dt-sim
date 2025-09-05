"""
simulators/dtc_simulator.py - Clean Pipeline DTC Simulator

Implements the user's clean architecture vision:
- Unified Data Pipeline orchestration
- Clean separation between preprocessing, parsing, and generation
- Intermediate representation for optimized text generation
- Pure pipeline architecture without legacy dependencies

Pipeline Flow:
1. Preprocessing (dtc_preprocessor) - Handle includes and macros
2. Parsing (dtc_parser) - Generate AST from processed content  
3. IR Building (core/intermediate) - Create intermediate representation with override merging
4. Generation (generators/dtb_text_generator) - Generate DTB text from IR
"""

import os
import time
from typing import Tuple, Optional
from pathlib import Path


class DTCSimulator:
    """Clean Pipeline DTC Simulator - Unified orchestration layer"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.include_paths = []
        
    def add_include_path(self, path: str):
        """Add include search path"""
        if path and os.path.exists(path):
            abs_path = os.path.abspath(path)
            if abs_path not in self.include_paths:
                self.include_paths.append(abs_path)
    
    def compile_dts(self, dts_file: str, output_file: str, 
                   platform: str = None, validate: bool = False, 
                   no_warnings: bool = False) -> Tuple[bool, Optional[object]]:
        """
        Compile DTS file using clean pipeline architecture
        
        Pipeline: Preprocessing → Parsing → IR Building → Text Generation
        
        Args:
            dts_file: Source DTS file path
            output_file: Output DTB text file path  
            platform: Target platform (auto-detected if None)
            validate: Enable validation
            no_warnings: Suppress warnings
            
        Returns:
            (success, intermediate_representation) tuple
        """
        
        start_time = time.time()
        
        try:
            if self.verbose:
                print(f"dt-sim dtc: compiling {dts_file} → {output_file}")
                print(f"Pipeline: Preprocessing → Parsing → IR Building → Text Generation")
                print(f"Started at: {time.strftime('%H:%M:%S')}")
                
            # ===== PHASE 1: PREPROCESSING =====
            phase_start = time.time()
            if self.verbose:
                print("  Phase 1: Preprocessing includes and macros...")
            
            processed_content = self._run_preprocessing_phase(dts_file, platform)
            
            if self.verbose:
                phase_time = time.time() - phase_start
                print(f"    [OK] Preprocessing completed in {phase_time:.3f}s")
                
            # ===== PHASE 2: PARSING =====
            phase_start = time.time() 
            if self.verbose:
                print("  Phase 2: Parsing DTS to AST...")
                print(f"    Processing {len(processed_content)} characters")
            
            device_tree = self._run_parsing_phase(processed_content, dts_file)
            
            if self.verbose:
                phase_time = time.time() - phase_start
                chars_per_sec = len(processed_content) / phase_time if phase_time > 0 else 0
                print(f"    [OK] Parsing completed in {phase_time:.3f}s ({chars_per_sec:.0f} chars/sec)")
                
            # ===== PHASE 3: IR BUILDING =====
            phase_start = time.time()
            if self.verbose:
                print("  Phase 3: Building intermediate representation...")
                
            intermediate_rep = self._run_ir_building_phase(device_tree)
            
            if self.verbose:
                phase_time = time.time() - phase_start
                print(f"    [OK] IR building completed in {phase_time:.3f}s")
                print(f"    Built IR with {intermediate_rep.metadata['node_count']} nodes, {intermediate_rep.metadata['label_count']} labels")
                
            # ===== PHASE 4: VALIDATION (Optional) =====
            if validate:
                phase_start = time.time()
                if self.verbose:
                    print("  Phase 4a: Validating intermediate representation...")
                    
                validation_errors = self._run_validation_phase(intermediate_rep)
                
                if self.verbose:
                    phase_time = time.time() - phase_start
                    print(f"    [OK] Validation completed in {phase_time:.3f}s")
                    if validation_errors and not no_warnings:
                        print(f"    Found {len(validation_errors)} validation issues")
                        for error in validation_errors:
                            print(f"      {error}")
                    
            # ===== PHASE 4/5: TEXT GENERATION =====
            phase_start = time.time()
            if self.verbose:
                phase_name = "Phase 5" if validate else "Phase 4"
                print(f"  {phase_name}: Generating DTB text output...")
            
            self._run_generation_phase(intermediate_rep, output_file, dts_file)
            
            if self.verbose:
                phase_time = time.time() - phase_start
                print(f"    [OK] Text generation completed in {phase_time:.3f}s")
                
            # ===== COMPLETION =====
            total_time = time.time() - start_time
            
            print("Compilation completed successfully!")
            print(f"   Node count: {intermediate_rep.metadata['node_count']}")
            print(f"   Label count: {intermediate_rep.metadata['label_count']}")
            print(f"   Override merging: {'Yes' if intermediate_rep.metadata['has_overrides'] else 'No'}")
            print(f"   Output file: {os.path.basename(output_file)}")
            print(f"   Total time: {total_time:.3f}s")
            
            return True, intermediate_rep
            
        except Exception as e:
            print(f"[ERROR] Compilation failed: {dts_file}")
            print(f"   Error: {str(e)}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return False, None
    
    # ===== PIPELINE PHASE METHODS =====
    
    def _run_preprocessing_phase(self, dts_file: str, platform: str = None) -> str:
        """Phase 1: Run preprocessing with includes and macros"""
        from parsers.dtc_preprocessor import PreprocessorV2
        
        preprocessor = PreprocessorV2(verbose=self.verbose)
        
        # Add include paths
        base_dir = os.path.dirname(os.path.abspath(dts_file))
        preprocessor.add_include_path(base_dir)
        for path in self.include_paths:
            preprocessor.add_include_path(path)
        
        # Process file with platform-specific bindings
        processed_content = preprocessor.process_file(dts_file, base_dir, platform=platform)
        
        if self.verbose:
            print(f"    Processed {len(processed_content)} characters")
        
        return processed_content
    
    def _run_parsing_phase(self, content: str, filename: str):
        """Phase 2: Parse preprocessed content to AST"""
        from parsers.dtc_parser import RecursiveDescentParser
        
        parser = RecursiveDescentParser(verbose=self.verbose)
        device_tree = parser.parse(content, filename)
        
        if self.verbose and device_tree.root:
            # Show basic tree stats
            node_count = self._count_ast_nodes(device_tree.root)
            print(f"    Built AST with {node_count} nodes")
        
        return device_tree
    
    def _run_ir_building_phase(self, device_tree):
        """Phase 3: Build intermediate representation with override merging"""
        from core.intermediate import IRBuilder
        
        ir_builder = IRBuilder(verbose=self.verbose)
        intermediate_rep = ir_builder.build_from_ast(device_tree)
        
        return intermediate_rep
    
    def _run_validation_phase(self, intermediate_rep) -> list:
        """Phase 4: Validate intermediate representation"""
        from core.intermediate import validate_ir
        
        validation_errors = validate_ir(intermediate_rep)
        
        if self.verbose:
            print(f"    Validation found {len(validation_errors)} issues")
        
        return validation_errors
    
    def _run_generation_phase(self, intermediate_rep, output_file: str, source_file: str):
        """Phase 4/5: Generate DTB text directly from intermediate representation"""
        from generators.dtb_text_generator import DTBTextGenerator
        
        generator = DTBTextGenerator(verbose=self.verbose)
        
        # Generate directly from IR - no conversion needed!
        generator.generate_from_ir(intermediate_rep, output_file, source_file)
    
    # ===== HELPER METHODS =====
    
    def _count_ast_nodes(self, node) -> int:
        """Count nodes in AST format (temporary helper)"""
        if not node:
            return 0
            
        count = 1
        if hasattr(node, 'children') and node.children:
            for child in node.children:
                count += self._count_ast_nodes(child)
                
        return count
    
