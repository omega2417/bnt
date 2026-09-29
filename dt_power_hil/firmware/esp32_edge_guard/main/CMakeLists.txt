idf_component_register(SRCS "edge_guard.c"
                       INCLUDE_DIRS "."
                       REQUIRES driver esp_timer mqtt json)
