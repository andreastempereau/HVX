# Helmet Project - File Structure & Cleanup Analysis

## Quick Start

Three comprehensive analysis documents have been created to help you understand the project structure and plan a cleanup:

1. **[FILE_STRUCTURE_ANALYSIS.md](FILE_STRUCTURE_ANALYSIS.md)** - Complete technical breakdown
2. **[CLEANUP_PLAN.txt](CLEANUP_PLAN.txt)** - Quick reference guide  
3. **[STRUCTURE_VISUAL.txt](STRUCTURE_VISUAL.txt)** - Visual architecture diagrams

## What Each Document Contains

### FILE_STRUCTURE_ANALYSIS.md (20 KB)
**The comprehensive reference document**

Contains:
- Complete directory structure with annotations
- Purpose of each component
- Files to KEEP with detailed justification
- Files to REMOVE with reasoning
- gRPC service architecture explanation
- Refactoring requirements (5 major updates needed)
- Key metrics and statistics
- Phase-by-phase cleanup plan

Best for: Deep understanding of the entire system

### CLEANUP_PLAN.txt (9 KB)  
**The execution roadmap**

Contains:
- Executive summary of project stats
- Keep/Remove lists in easy-to-scan format
- Refactoring checklist (5 items)
- Phase-by-phase execution guide (8 phases, 3-4 hours total)
- Impact analysis (pros/cons, risk level)
- Estimated effort breakdown

Best for: Planning your cleanup approach

### STRUCTURE_VISUAL.txt (10 KB)
**The architecture diagrams**

Contains:
- Current microservices architecture diagram
- Target monolithic architecture diagram
- File tree with status labels
- Code statistics table
- Removal impact metrics

Best for: Visual learners, architecture overview

## Key Findings

### Project Composition
- **Total**: 9,527 lines of Python code
- **Keep**: 7,400 lines (UI + utils)
- **Remove**: 2,934 lines (backend services)
- **Reduction**: 22% smaller codebase

### Architecture Change
**FROM**: 5 separate processes communicating via gRPC
```
VideoService (50051) ──┐
PerceptionService (50052) ├─ OrchestratorService ─── Visor UI
VoiceService (50053) ──┘
```

**TO**: Single monolithic process
```
Visor UI
├─ Direct Camera Access
├─ Direct YOLO Detection
├─ Direct Voice Processing  
├─ Direct IMU/GPS Access
└─ Local State Management
```

### Files to Keep
- **apps/visor-ui/** - Entire directory (30 Python + 14 QML files)
- **libs/utils/** - Configuration and logging
- **configs/profiles/** - All configuration files
- **Documentation** - All README, guides, and reviews
- **Test scripts** - All testing utilities

### Files to Remove
- **services/** - All 5 backend services (2,934 lines)
- **libs/messages/** - gRPC protocol definitions
- **.map_cache/** - Generated map tiles
- **models/yolov4.weights** - Legacy 45MB model file
- Deployment files for removed services

## Refactoring Summary

After removing services, 5 main updates needed in visor-ui:

| Component | Current | Target | Effort |
|-----------|---------|--------|--------|
| Video | gRPC client → VideoService | direct_camera.py | Low |
| Detection | gRPC client → PerceptionService | Direct YOLO import | Medium |
| Voice | gRPC client (PARTIAL) | openai_voice_assistant.py | Minimal |
| GPS | gRPC client → GPSService | Direct serial access | Low |
| State | gRPC client → OrchestratorService | LocalStateMachine | Medium |

## Risk Assessment

**Risk Level: LOW**

- UI already has direct hardware handlers
- Service clients are thin wrappers
- No loss of functionality
- All hardware drivers unchanged
- Complete test infrastructure present

## Time Estimate

- Phase 1-4 (Delete + Update deploy): 20 minutes
- Phase 5 (Refactor UI): 90-120 minutes [MAIN EFFORT]
- Phase 6-8 (Docs + Test + Commit): 75 minutes
- **Total: 3-4 hours**

## How to Use These Documents

### For Initial Understanding
1. Start with **STRUCTURE_VISUAL.txt** for the big picture
2. Review the architecture diagrams
3. Scan the file tree with status labels

### For Implementation Planning  
1. Read **CLEANUP_PLAN.txt** sections in order
2. Follow the execution phases (1-8)
3. Use the refactoring checklist

### For Detailed Reference
1. Keep **FILE_STRUCTURE_ANALYSIS.md** open while coding
2. Refer to specific component sections
3. Check refactoring requirements

## Key Insight

The project is **well-structured** for this cleanup:
- Clear separation between UI and services
- UI has standalone hardware handlers (no new code needed)
- Refactoring uses existing code, not new logic
- Low risk of introducing bugs
- Phased approach allows testing at each step

## Next Steps

1. **Review** the analysis documents
2. **Create branch**: `git checkout -b cleanup/remove-services`
3. **Plan** using CLEANUP_PLAN.txt checklist
4. **Execute** the 8 phases
5. **Test** each component thoroughly
6. **Document** any changes
7. **Create PR** with migration notes

---

**Created**: November 20, 2025  
**Analysis Scope**: /home/hvx/HVX/helmet/  
**Status**: Ready for implementation
