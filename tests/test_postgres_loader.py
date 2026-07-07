import pandas as pd

from db_profiler.loaders import load_postgres_tables


class FakeScalarResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class FakeConnection:
    def __init__(self) -> None:
        self.executed_sql = []

    def execute(self, statement):
        self.executed_sql.append(str(statement))
        return FakeScalarResult(250000)


class FakeConnectionContext:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def __enter__(self) -> FakeConnection:
        return self.connection

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


class FakePreparer:
    def quote_schema(self, value: str) -> str:
        return f'"{value}"'

    def quote(self, value: str) -> str:
        return f'"{value}"'


class FakeDialect:
    identifier_preparer = FakePreparer()


class FakeEngine:
    dialect = FakeDialect()

    def __init__(self) -> None:
        self.connection = FakeConnection()

    def connect(self):
        return FakeConnectionContext(self.connection)


class FakeInspector:
    def get_table_names(self, schema: str):
        assert schema == "public"
        return ["customers"]


def test_load_postgres_tables_gets_exact_count_and_sampled_dataframe() -> None:
    engine = FakeEngine()

    def fake_read_sql_query(statement, connection, params):
        assert 'SELECT * FROM "public"."customers" LIMIT :sample_rows' == str(statement)
        assert params == {"sample_rows": 50000}
        return pd.DataFrame({"id": [1, 2, 3]})

    tables, metadata = load_postgres_tables(
        database_url="postgresql+psycopg://user:pass@localhost:5432/demo",
        schema="public",
        sample_rows=50000,
        engine_factory=lambda _: engine,
        inspector_factory=lambda _: FakeInspector(),
        read_sql_query=fake_read_sql_query,
    )

    assert list(tables) == ["customers"]
    assert len(tables["customers"]) == 3
    assert engine.connection.executed_sql == ['SELECT COUNT(*) FROM "public"."customers"']
    assert metadata["customers"]["source"] == "postgres"
    assert metadata["customers"]["source_row_count"] == 250000
    assert metadata["customers"]["sample_count"] == 3
    assert metadata["customers"]["sample_row_limit"] == 50000


def test_load_postgres_tables_uses_include_table_allowlist() -> None:
    engine = FakeEngine()

    def fake_read_sql_query(statement, connection, params):
        return pd.DataFrame({"id": [1]})

    tables, _metadata = load_postgres_tables(
        database_url="postgresql+psycopg://user:pass@localhost:5432/demo",
        schema="public",
        sample_rows=10,
        include_tables=["orders"],
        engine_factory=lambda _: engine,
        inspector_factory=lambda _: (_ for _ in ()).throw(AssertionError("inspector should not be used")),
        read_sql_query=fake_read_sql_query,
    )

    assert list(tables) == ["orders"]
    assert engine.connection.executed_sql == ['SELECT COUNT(*) FROM "public"."orders"']
