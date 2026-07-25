from __future__ import annotations

import pandas as pd

from sparkstagelapse.dashboard.templates import table_to_html



def test_table_to_html_escapes_title():
    pdf = pd.DataFrame({"a": [1]})
    html = table_to_html(pdf, "<script>alert(1)</script>", "tbl_esc")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
