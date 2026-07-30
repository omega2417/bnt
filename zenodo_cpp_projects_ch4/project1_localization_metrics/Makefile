# Build the reference implementation of Section 4.4 (Localization-Quality Evaluation).
CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra
TARGET   := localization_metrics
.PHONY: all run clean
all: $(TARGET)
$(TARGET): src/main.cpp
	$(CXX) $(CXXFLAGS) src/main.cpp -o $(TARGET)
run: $(TARGET)
	./$(TARGET)
clean:
	rm -f $(TARGET)
