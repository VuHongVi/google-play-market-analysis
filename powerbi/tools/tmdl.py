"""Tiny TMDL writer: one Import table per CSV in powerbi/data, plus a _Measures table."""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pandas as pd

NS = uuid.UUID("6f1c2b8e-1d0a-4c55-9b0e-5a3e2f7d9c11")


def tag(*parts: str) -> str:
    return str(uuid.uuid5(NS, "/".join(parts)))


def q(name: str) -> str:
    """Quote a TMDL object name when needed."""
    return f"'{name}'" if any(ch in name for ch in " ()-%/.") or name[0].isdigit() else name


def _col_type(s: pd.Series) -> tuple[str, str]:
    if pd.api.types.is_integer_dtype(s) or (pd.api.types.is_float_dtype(s) and s.dropna().mod(1).eq(0).all() and s.name.endswith(("_order", "rank"))):
        return "int64", "Int64.Type"
    if pd.api.types.is_float_dtype(s):
        return "double", "type number"
    if s.name in ("last_updated",):
        return "dateTime", "type date"
    return "string", "type text"


def _table(model: str, name: str, df: pd.DataFrame, formats: dict, sort_by: dict, hidden: set) -> str:
    lines = [f"table {q(name)}", f"\tlineageTag: {tag(model, name)}", ""]
    m_types = []
    for c in df.columns:
        dt, mt = _col_type(df[c])
        m_types.append(f'{{"{c}", {mt}}}')
        lines += [f"\tcolumn {q(c)}", f"\t\tdataType: {dt}"]
        if c in formats:
            lines.append(f"\t\tformatString: {formats[c]}")
        elif dt == "int64":
            lines.append("\t\tformatString: 0")
        if c in hidden:
            lines.append("\t\tisHidden")
        if c in sort_by and sort_by[c] in df.columns:
            lines.append(f"\t\tsortByColumn: {q(sort_by[c])}")
        lines += [f"\t\tlineageTag: {tag(model, name, c)}", "\t\tsummarizeBy: none", f"\t\tsourceColumn: {c}", ""]
    src = (f'Csv.Document(File.Contents(CsvFolder & "{name}.csv"), [Delimiter=",", Columns={len(df.columns)}, '
           f'Encoding=65001, QuoteStyle=QuoteStyle.Csv])')
    lines += [
        f"\tpartition {q(name)} = m", "\t\tmode: import", "\t\tsource =", "\t\t\t\tlet",
        f"\t\t\t\t    Source = {src},",
        "\t\t\t\t    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
        f"\t\t\t\t    Typed = Table.TransformColumnTypes(Promoted, {{{', '.join(m_types)}}}, \"en-US\")",
        "\t\t\t\tin", "\t\t\t\t    Typed", "",
    ]
    return "\n".join(lines) + "\n"


def _measures(model: str, measures: list) -> str:
    lines = ["/// Home table for every report measure.", "table _Measures", f"\tlineageTag: {tag(model, '_Measures')}", ""]
    for name, expr, fmt, folder, desc in measures:
        if desc:
            lines.append(f"\t/// {desc}")
        lines += [f"\tmeasure {q(name)} = {expr}", f"\t\tformatString: {fmt}", f"\t\tdisplayFolder: {folder}",
                  f"\t\tlineageTag: {tag(model, 'measure', name)}", ""]
    lines += ["\tcolumn Value", "\t\tdataType: int64", "\t\tisHidden", "\t\tformatString: 0",
              f"\t\tlineageTag: {tag(model, '_Measures', 'Value')}", "\t\tsummarizeBy: none", "\t\tsourceColumn: Value", "",
              "\tpartition _Measures = m", "\t\tmode: import", "\t\tsource =", "\t\t\t\tlet",
              "\t\t\t\t    Source = #table(type table [Value = Int64.Type], {})", "\t\t\t\tin", "\t\t\t\t    Source", ""]
    return "\n".join(lines) + "\n"


def write_model(root: Path, model: str, formats: dict, sort_by: dict, hidden: set, measures: list) -> None:
    data = root / "data"
    sm = root / f"{model}.SemanticModel"
    d = sm / "definition"
    if (d / "tables").exists():
        shutil.rmtree(d / "tables")
    (d / "tables").mkdir(parents=True)
    csvs = sorted(data.glob("*.csv"))
    names = [p.stem for p in csvs]
    for p in csvs:
        df = pd.read_csv(p)
        (d / "tables" / f"{p.stem}.tmdl").write_text(_table(model, p.stem, df, formats, sort_by, hidden), encoding="utf-8")
    (d / "tables" / "_Measures.tmdl").write_text(_measures(model, measures), encoding="utf-8")

    folder = str(data.resolve()) + "\\"
    (d / "expressions.tmdl").write_text(
        f"/// Local folder with the CSV tables written by the Python pipeline. Change this one value if the repo moves.\n"
        f'expression CsvFolder = "{folder}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {tag(model, 'CsvFolder')}\n\n\tannotation PBI_ResultType = Text\n\n", encoding="utf-8")
    order = json.dumps(names + ["_Measures", "CsvFolder"])
    (d / "model.tmdl").write_text(
        "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tsourceQueryCulture: en-US\n"
        "\tdataAccessOptions\n\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
        "annotation __PBI_TimeIntelligenceEnabled = 0\n\n"
        f"annotation PBI_QueryOrder = {order}\n\n"
        + "".join(f"ref table {q(n)}\n" for n in names + ["_Measures"]), encoding="utf-8")
    (d / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1606\n\n", encoding="utf-8")
    (sm / "definition.pbism").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}}, indent=2) + "\n", encoding="utf-8")
    (sm / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": model},
        "config": {"version": "2.0", "logicalId": tag(model, "logicalId", "SemanticModel")}}, indent=2) + "\n", encoding="utf-8")
    print(f"{model}: {len(names)} tables + _Measures ({len(measures)} measures) -> {sm}")
