# Minimal Sphinx makefile.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

strict:
	@$(SPHINXBUILD) -W --keep-going -b html "$(SOURCEDIR)" "$(BUILDDIR)/html" $(SPHINXOPTS) $(O)

live:
	sphinx-autobuild "$(SOURCEDIR)" "$(BUILDDIR)/html" --ignore "*/_generated/*" $(SPHINXOPTS) $(O)

clean:
	rm -rf "$(BUILDDIR)" _generated

.PHONY: help strict live clean Makefile

%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
