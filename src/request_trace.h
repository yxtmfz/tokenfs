#pragma once
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <mutex>
#include <string>
#include <vector>
#include <time.h>

// Optional diagnostic only. CLOCK_MONOTONIC matches the Linux Python loader.
// Bounded records and bounded strings; no filesystem writes in the hot path.
class RequestTrace {
 public:
  struct Event {
    std::string op, path, tier;
    uint64_t handle=0,start_ns=0,end_ns=0,wait_ns=0,pread_ns=0,flush_ns=0;
    uint64_t copy_ns=0,verify_ns=0,bytes=0,selected_ns=0;
    int location=-1;
    int caller=-1;
  };
  static uint64_t Now() {
    timespec t{};clock_gettime(CLOCK_MONOTONIC,&t);
    return uint64_t(t.tv_sec)*1000000000ULL+t.tv_nsec;
  }
  explicit RequestTrace(std::string output={},size_t limit=32768)
      :output_(std::move(output)),limit_(limit) {if(Enabled())events_.reserve(limit_);}
  bool Enabled() const {return !output_.empty();}
  void Add(Event e) {
    if(!Enabled())return;
    e.op.resize(std::min<size_t>(e.op.size(),32));
    e.path.resize(std::min<size_t>(e.path.size(),512));
    e.tier.resize(std::min<size_t>(e.tier.size(),32));
    std::lock_guard<std::mutex> lock(mu_);
    if(events_.size()<limit_)events_.push_back(std::move(e));else ++dropped_;
  }
  static std::string Quote(const std::string& s) {
    std::string out="\"";const char* hex="0123456789abcdef";
    for(unsigned char c:s) {
      if(c=='"'||c=='\\'){out+='\\';out+=char(c);}
      else if(c<32){out+="\\u00";out+=hex[c>>4];out+=hex[c&15];}
      else out+=char(c);
    }
    return out+'"';
  }
  bool Dump() {
    if(!Enabled())return true;
    std::lock_guard<std::mutex> lock(mu_);std::ofstream f(output_);
    f<<"{\"clock\":\"CLOCK_MONOTONIC\",\"limit\":"<<limit_<<",\"dropped\":"<<dropped_<<",\"events\":[";
    bool first=true;
    for(const auto& e:events_) {
      if(!first)f<<',';
      first=false;
      f<<"{\"op\":"<<Quote(e.op)<<",\"path\":"<<Quote(e.path)<<",\"tier\":"<<Quote(e.tier)
       <<",\"location\":"<<e.location<<",\"selected_ns\":"<<e.selected_ns
       <<",\"handle\":"<<e.handle<<",\"caller\":"<<e.caller<<",\"start_ns\":"<<e.start_ns
       <<",\"end_ns\":"<<e.end_ns<<",\"wait_ns\":"<<e.wait_ns<<",\"pread_ns\":"<<e.pread_ns
       <<",\"flush_ns\":"<<e.flush_ns<<",\"copy_ns\":"<<e.copy_ns<<",\"verify_ns\":"<<e.verify_ns<<",\"bytes\":"<<e.bytes<<'}';
    }
    f<<"]}\n";f.flush();return bool(f);
  }
  class Span {
   public:
    Event e;
    Span(RequestTrace& trace,const char* op):trace_(trace),enabled_(trace.Enabled()) {
      if(enabled_){e.op=op;e.start_ns=Now();}
    }
    ~Span(){Finish();}
    // End a planning span before execution; all early returns still close it.
    void Finish(){if(enabled_ && !finished_){e.end_ns=Now();trace_.Add(std::move(e));finished_=true;}}
    bool Enabled() const{return enabled_;}
    Span(const Span&)=delete;Span& operator=(const Span&)=delete;
   private:RequestTrace& trace_;bool enabled_;bool finished_=false;
  };
 private:
  std::string output_;size_t limit_;uint64_t dropped_=0;
  std::mutex mu_;std::vector<Event> events_;
};
