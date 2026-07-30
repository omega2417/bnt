# Build the reference implementation of Section 3.3 (Adaptive Sensor Weighting).
# Requires only a C++17 compiler and the standard library.
CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra
TARGET   := adaptive_weighting

.PHONY: all run clean
all: $(TARGET)

$(TARGET): src/main.cpp
	$(CXX) $(CXXFLAGS) src/main.cpp -o $(TARGET)

run: $(TARGET)
	./$(TARGET)

clean:
	rm -f $(TARGET)
