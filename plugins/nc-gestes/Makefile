# nc-gestes : plugin Hyprland (gestes d'ouverture). Nécessite les en-têtes d'Hyprland (pkg-config hyprland).
CXX      ?= g++
CXXFLAGS ?= -O2
SORTIE   ?= nc-gestes.so

HYPR_CFLAGS := $(shell pkg-config --cflags hyprland)
SOURCES     := $(wildcard src/*.cpp)
ENTETES     := $(wildcard src/*.hpp)

# Pas de -fvisibility=hidden : les globales « inline » d'Hyprland (g_pHyprRenderer…) doivent se lier
# à celles de l'exécutable, pas à une copie privée vide.
# -fno-gnu-unique : sans lui, glibc ne décharge jamais le .so et « plugin unload » ne prouverait rien.
override CXXFLAGS += -std=c++23 -shared -fPIC -fno-gnu-unique -Wall -Wextra -DWLR_USE_UNSTABLE $(HYPR_CFLAGS)

all: $(SORTIE)

$(SORTIE): $(SOURCES) $(ENTETES) Makefile
	@pkg-config --exists hyprland || { echo "nc-gestes : en-têtes d'Hyprland introuvables (pkg-config hyprland)" >&2; exit 1; }
	$(CXX) $(CXXFLAGS) $(SOURCES) -o $@

clean:
	rm -f $(SORTIE)

.PHONY: all clean
