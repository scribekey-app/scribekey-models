# Builds the recorder against the llama.cpp revision the Android app pins
# (app/src/main/cpp/CMakeLists.txt, SCRIBEKEY_LLAMA_CPP_REVISION). Pass its checkout:
#   cmake -S . -B build -DLLAMA_CPP_DIR=/path/to/scribekey/third_party/llama.cpp
cmake_minimum_required(VERSION 3.14)
project(cleanup_example_recorder CXX C)
set(LLAMA_CPP_DIR "" CACHE PATH "llama.cpp checkout at the app's pinned revision")
if(NOT LLAMA_CPP_DIR)
    message(FATAL_ERROR "Set -DLLAMA_CPP_DIR to the app's third_party/llama.cpp checkout")
endif()
set(LLAMA_CURL OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_SERVER OFF CACHE BOOL "" FORCE)
set(GGML_NATIVE OFF CACHE BOOL "" FORCE)
add_subdirectory(${LLAMA_CPP_DIR} llama)
add_executable(recorder recorder.cpp)
target_link_libraries(recorder PRIVATE llama)
target_compile_features(recorder PRIVATE cxx_std_17)
