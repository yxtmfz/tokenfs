#pragma once
#include <cstdint>
#include <stdexcept>

// All components are measured wall time. Capture and admission planning have
// finished before the commit decision; eviction, writes, verification and READY
// publication remain payable. Do not discount the latter merely for being async.
struct CopyCostSample {
  uint64_t pipeline_us, planning_us, capture_us;
  uint64_t Full() const { return pipeline_us + capture_us; }
  uint64_t Remaining() const {
    if(planning_us>pipeline_us)throw std::logic_error("copy planning exceeds pipeline");
    return pipeline_us-planning_us;
  }
  uint64_t Charge(bool incremental) const {return incremental?Remaining():Full();}
};
