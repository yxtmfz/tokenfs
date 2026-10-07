cmake_minimum_required(VERSION 3.20)
project(tokenfs LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(FUSE3 REQUIRED fuse3)
find_package(yaml-cpp REQUIRED)
find_package(SQLite3 REQUIRED)

add_executable(tokenfs
  src/main.cpp
)

target_include_directories(tokenfs PRIVATE
  ${FUSE3_INCLUDE_DIRS}
)

target_compile_options(tokenfs PRIVATE
  ${FUSE3_CFLAGS_OTHER}
  -Wall
  -Wextra
  -Wpedantic
)

target_link_libraries(tokenfs PRIVATE
  ${FUSE3_LIBRARIES}
  yaml-cpp
  SQLite::SQLite3
)

include(CTest)
if(BUILD_TESTING)
  add_executable(aligned_read_test tests/aligned_read_test.cpp)
  target_compile_options(aligned_read_test PRIVATE -UNDEBUG)
  add_test(NAME aligned_read COMMAND aligned_read_test)
  add_executable(disk_opportunity_test tests/disk_opportunity_test.cpp)
  target_compile_options(disk_opportunity_test PRIVATE -UNDEBUG)
  add_test(NAME disk_opportunity COMMAND disk_opportunity_test)
  add_executable(run_reuse_test tests/run_reuse_test.cpp)
  target_compile_options(run_reuse_test PRIVATE -UNDEBUG)
  add_test(NAME run_reuse COMMAND run_reuse_test)
  add_executable(burst_interval_test tests/burst_interval_test.cpp)
  target_compile_options(burst_interval_test PRIVATE -UNDEBUG)
  add_test(NAME burst_interval COMMAND burst_interval_test)
  add_executable(planning_equivalence_test tests/planning_equivalence_test.cpp)
  target_compile_options(planning_equivalence_test PRIVATE -UNDEBUG)
  add_test(NAME planning_equivalence COMMAND planning_equivalence_test)
  add_executable(copy_cost_test tests/copy_cost_test.cpp)
  target_compile_options(copy_cost_test PRIVATE -UNDEBUG)
  add_test(NAME copy_cost COMMAND copy_cost_test)
  add_executable(request_read_cost_test tests/request_read_cost_test.cpp)
  target_compile_options(request_read_cost_test PRIVATE -UNDEBUG)
  add_test(NAME request_read_cost COMMAND request_read_cost_test)
  add_executable(read_fill_test tests/read_fill_test.cpp)
  target_compile_options(read_fill_test PRIVATE -UNDEBUG)
  add_test(NAME read_fill COMMAND read_fill_test)
  add_executable(request_trace_test tests/request_trace_test.cpp)
  target_compile_options(request_trace_test PRIVATE -UNDEBUG)
  add_test(NAME request_trace COMMAND request_trace_test)
  add_executable(policy_metadata_test tests/policy_metadata_test.cpp)
  target_include_directories(policy_metadata_test PRIVATE ${FUSE3_INCLUDE_DIRS})
  target_compile_options(policy_metadata_test PRIVATE ${FUSE3_CFLAGS_OTHER} -UNDEBUG)
  target_link_libraries(policy_metadata_test PRIVATE ${FUSE3_LIBRARIES} yaml-cpp SQLite::SQLite3)
  add_test(NAME policy_metadata COMMAND policy_metadata_test)
  add_executable(measured_policy_test tests/measured_policy_test.cpp)
  target_compile_options(measured_policy_test PRIVATE -UNDEBUG)
  add_test(NAME measured_policy COMMAND measured_policy_test)
  add_executable(sieve_policy_test tests/sieve_policy_test.cpp)
  target_compile_options(sieve_policy_test PRIVATE -UNDEBUG)
  add_test(NAME sieve_policy COMMAND sieve_policy_test)
endif()
