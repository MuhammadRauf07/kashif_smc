import codecs
import os
import sys


def _is_streamlit_entrypoint():
    """True when Streamlit Cloud (or `streamlit run`) is executing this file."""
    main = sys.modules.get("__main__")
    main_file = getattr(main, "__file__", None)
    if not main_file:
        return False
    same_file = os.path.abspath(main_file) == os.path.abspath(__file__)
    # ScriptRunner replaces sys.modules["__main__"] before exec, and that
    # module is already imported by the time the app file starts.
    return same_file and "streamlit.runtime.scriptrunner" in sys.modules


def _render_streamlit_app():
    from streamlit_app import render

    render()


if _is_streamlit_entrypoint():
    _render_streamlit_app()
else:
    from setuptools import setup

    VERSION = "0.0.27"
    DESCRIPTION = "Getting indicators based on smart money concepts or ICT"

    with codecs.open("README.md", encoding="utf-8") as f:
        LONG_DESCRIPTION = f.read()

    setup(
        name="smartmoneyconcepts",
        version=VERSION,
        author="Joshua Attridge",
        description=DESCRIPTION,
        long_description_content_type="text/markdown",
        long_description=LONG_DESCRIPTION,
        packages=["smartmoneyconcepts"],
        install_requires=["pandas>=2.0.2", "numpy>=1.24.3", "numba>=0.58.1"],
        keywords=[
            "smart",
            "money",
            "concepts",
            "ict",
            "indicators",
            "trading",
            "forex",
            "stocks",
            "crypto",
            "order",
            "blocks",
            "liquidity",
        ],
        url="https://github.com/joshyattridge/smartmoneyconcepts",
        classifiers=[
            "Development Status :: 1 - Planning",
            "Intended Audience :: Developers",
            "Programming Language :: Python :: 3",
            "Operating System :: Unix",
            "Operating System :: MacOS :: MacOS X",
            "Operating System :: Microsoft :: Windows",
        ],
    )
