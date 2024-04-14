cmake_minimum_required (VERSION 3.13)

project(someipy_test_apps)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14")

find_package(vsomeip3 CONFIG REQUIRED)

# TODO: Common function for building a single test target
function(add_test_app_target)


    
endfunction(add_test_app_target)


add_executable(send_events_udp send_events_udp/send_events_udp.cpp)
target_link_libraries(send_events_udp ${VSOMEIP_LIBRARIES} pthread)

set(CMAKE_INSTALL_PREFIX "${CMAKE_SOURCE_DIR}/install")

install(TARGETS send_events_udp
    RUNTIME DESTINATION send_events_udp)

file(GLOB JSON_FILES "${CMAKE_SOURCE_DIR}/send_events_udp/*.json" "${CMAKE_SOURCE_DIR}/send_events_udp/*.sh")
install(FILES ${JSON_FILES} DESTINATION send_events_udp)