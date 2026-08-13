"""
The trust chain: the checks every AI-extracted result must pass before
anything downstream is allowed to treat it as real data. Nothing here
knows or cares what a "normal" value looks like for any given test -
these are structural/format checks only (does the value actually
appear in its own OCR evidence, is it well-formed, is the confidence
high enough) - never a medical judgment about the value itself.
"""
