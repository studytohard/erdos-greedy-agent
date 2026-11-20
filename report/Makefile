# Build the report with XeLaTeX (TeX Live 2025 or later).
#
#   make            -> report.pdf
#   make clean      -> remove auxiliary files
#   make distclean  -> remove auxiliary files and report.pdf

LATEX = latexmk -xelatex -interaction=nonstopmode -halt-on-error

.PHONY: all clean distclean

all: report.pdf

report.pdf: report.tex figures/agent_loop.png figures/failure_residue.png \
            figures/growth.png figures/height_ratio.png figures/heights.png \
            figures/k_distribution.png figures/obstruction_chain.png \
            figures/records.png
	$(LATEX) report.tex

clean:
	latexmk -c report.tex

distclean: clean
	-rm -f report.pdf
