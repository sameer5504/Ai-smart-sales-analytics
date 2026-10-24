from app.reports.service import get_report, list_reports, save_report


async def test_save_report_persists_and_returns_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    report = await save_report(user_id=1, data={"total": 100})

    assert report.user_id == 1
    assert report.data == {"total": 100}
    assert report.report_id

    saved_file = tmp_path / "reports" / "1" / f"{report.report_id}.json"
    assert saved_file.is_file()


async def test_list_reports_returns_only_that_users_reports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    await save_report(user_id=1, data={"total": 100})
    await save_report(user_id=1, data={"total": 200})
    await save_report(user_id=2, data={"total": 999})

    user_1_reports = await list_reports(user_id=1)
    user_2_reports = await list_reports(user_id=2)

    assert len(user_1_reports) == 2
    assert len(user_2_reports) == 1
    assert all(summary.user_id == 1 for summary in user_1_reports)


async def test_list_reports_is_empty_for_a_user_with_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    reports = await list_reports(user_id=1)

    assert reports == []


async def test_list_reports_summaries_have_no_data_field(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    await save_report(user_id=1, data={"total": 100})

    [summary] = await list_reports(user_id=1)

    assert not hasattr(summary, "data")


async def test_get_report_returns_the_saved_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    saved = await save_report(user_id=1, data={"total": 100})

    fetched = await get_report(user_id=1, report_id=saved.report_id)

    assert fetched == saved


async def test_get_report_raises_not_found_for_unknown_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    try:
        await get_report(user_id=1, report_id="does-not-exist")
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError:
        pass


async def test_get_report_raises_not_found_for_another_users_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    saved = await save_report(user_id=1, data={"total": 100})

    try:
        await get_report(user_id=2, report_id=saved.report_id)
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError:
        pass


async def test_get_report_rejects_a_path_traversal_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    try:
        await get_report(user_id=1, report_id="../../etc/passwd")
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError:
        pass
