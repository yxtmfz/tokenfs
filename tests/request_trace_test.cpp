#include "../src/request_trace.h"
#include <cassert>
#include <filesystem>
#include <thread>
#include <unistd.h>
int main(){
  auto p=std::filesystem::temp_directory_path()/("tokenfs-trace-test-"+std::to_string(getpid())+".json");
  RequestTrace disabled;assert(!disabled.Enabled() && disabled.Dump());
  RequestTrace trace(p.string(),2);
  {RequestTrace::Span span(trace,"read");span.e.path="quote\"\n\\";span.e.handle=9;}
  std::thread a([&]{RequestTrace::Span span(trace,"release");});a.join();
  {RequestTrace::Span dropped(trace,"excess");}
  assert(!std::filesystem::exists(p));assert(trace.Dump());
  std::ifstream f(p);std::string s((std::istreambuf_iterator<char>(f)),{});
  assert(s.find("\"dropped\":1")!=std::string::npos);
  assert(s.find("quote\\\"\\u000a\\\\")!=std::string::npos);
  assert(s.find("excess")==std::string::npos);
  std::filesystem::remove(p);
}
