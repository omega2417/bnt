# Build the reference implementation of Section 3.5 (Drift + FTM Anchoring).
# Requires only a C++17 compiler and the standard library.
CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra
TARGET   := drift_ftm_anchoring

.PHONY: all run clean
all: $(TARGET)

$(TARGET): src/main.cpp
	$(CXX) $(CXXFLAGS) src/main.cpp -o $(TARGET)

run: $(TARGET)
	./$(TARGET)

clean:
	rm -f $(TARGET)
