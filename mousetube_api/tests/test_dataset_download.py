"""The files of a Zenodo record and the zip of a dataset.

Zenodo is replaced by a stub: no request leaves the machine. What is checked: who may download
(signed-in users only, with a token valid once), what the zip holds (visible files held by Zenodo),
that nothing is left behind when a download ends (the places are given back, even when a file
fails or the visitor leaves), and that the server cannot be made to fetch from another host.
"""

import asyncio
import io
import zipfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from mousetube_api import views
from mousetube_api.models import (
    Dataset,
    File,
    Laboratory,
    Protocol,
    RecordingSession,
)
from mousetube_api.utils import zenodo_files

ZENODO = "https://zenodo.org/records/111/files/{}?download=1"


class FakeAnswer:
    """What `requests.get(..., stream=True)` gives, as a context manager."""

    def __init__(self, body=b"", fail=False, cut_after=None):
        self.body, self.fail, self.cut_after = body, fail, cut_after

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        if self.fail:
            raise zenodo_files.requests.HTTPError("503")

    def iter_content(self, size):
        body = self.body if self.cut_after is None else self.body[: self.cut_after]
        for start in range(0, len(body), 4):
            yield body[start : start + 4]

    def json(self):
        return self.body


class Base(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.owner = User.objects.create_user("own", "own@igbmc.fr", "x")
        self.other = User.objects.create_user("oth", "oth@igbmc.fr", "x")
        draft = {"status": "draft", "created_by": self.owner}
        self.protocol = Protocol.objects.create(
            name="P",
            animals_sex="male(s)",
            animals_age="pup",
            animals_housing="grouped",
            context_number_of_animals="2",
            context_duration="short term (<1h)",
            context_cage="unfamiliar test cage",
            context_bedding="bedding",
            context_light_cycle="day",
            **draft,
        )
        self.lab = Laboratory.objects.create(name="L", **draft)
        self.session = self.session_of("shared", "S1")
        self.dataset = Dataset.objects.create(name="Mouse set", created_by=self.owner)
        self.dataset.recording_session_list.add(self.session)
        self.client = APIClient()

    def session_of(self, state, name):
        return RecordingSession.objects.create(
            name=name,
            is_multiple=True,
            status=state,
            protocol=self.protocol,
            laboratory=self.lab,
            created_by=self.owner,
        )

    def file(self, name, link, size=None, session=None):
        return File.objects.create(
            name=name,
            link=link,
            size=size,
            recording_session=session or self.session,
            status="done",
            created_by=self.owner,
        )

    def url(self):
        return f"/api/dataset/{self.dataset.pk}/download/"

    def token(self, user=None, dataset=None):
        return signing.dumps(
            {"u": (user or self.owner).pk, "k": (dataset or self.dataset).pk},
            salt=views.DATASET_ZIP_SALT,
        )

    def download(self, user=None, token=None):
        """GET with a token: the answer, and the zip when there is one."""
        response = self.client.get(self.url(), {"token": token or self.token(user)})
        if response.status_code != 200:
            return response, None
        body = b"".join(response)  # the test client reads the whole stream
        return response, zipfile.ZipFile(io.BytesIO(body))


def stub(bodies):
    """`requests.get` that answers by address with `bodies` (address -> FakeAnswer)."""

    def get(url, **kwargs):
        return bodies[url]

    return get


class RecordLinks(TestCase):
    def test_only_zenodo_records_are_understood(self):
        self.assertEqual(
            zenodo_files.record_of(
                "https://zenodo.org/records/5/files/a.wav?download=1"
            ),
            ("zenodo.org", "5"),
        )
        self.assertEqual(
            zenodo_files.record_of("https://zenodo.org/record/5865521/files/a.wav"),
            ("zenodo.org", "5865521"),
        )
        self.assertEqual(
            zenodo_files.record_of("https://zenodo.org/api/records/7/files-archive"),
            ("zenodo.org", "7"),
        )
        self.assertEqual(
            zenodo_files.record_of("https://sandbox.zenodo.org/records/9"),
            ("sandbox.zenodo.org", "9"),
        )
        for link in (
            "https://evil.example/records/5/files/a.wav",
            "https://zenodo.org.evil.example/records/5/files/a.wav",
            "https://zenodo.org@evil.example/records/5/files/a.wav",
            "http://127.0.0.1/records/5/files/a.wav",
            "https://zenodo.org/communities/x",
            "ftp://zenodo.org/records/5/files/a.wav",
            "",
            None,
        ):
            self.assertIsNone(zenodo_files.record_of(link), link)

    def test_the_address_of_a_file_is_encoded(self):
        self.assertEqual(
            zenodo_files.file_url("zenodo.org", "5", "Female Rat 22kHz.wav"),
            "https://zenodo.org/records/5/files/Female%20Rat%2022kHz.wav?download=1",
        )

    def test_the_name_comes_from_the_link_when_it_has_one(self):
        self.assertEqual(
            zenodo_files.name_in(ZENODO.format("a%20b.wav"), "x.wav"), "a b.wav"
        )
        self.assertEqual(
            zenodo_files.name_in(
                "https://zenodo.org/api/records/7/files-archive", "x.wav"
            ),
            "x.wav",
        )


class ZenodoFilesList(Base):
    def setUp(self):
        super().setUp()
        self.f = self.file("a b.wav", ZENODO.format("a%20b.wav"))
        self.record = {
            "files": [
                {"key": "a b.wav", "size": 12},
                {"key": "a b_usvseg.csv", "size": 3},
            ]
        }

    def get(self, file=None):
        return self.client.get(f"/api/file/{(file or self.f).pk}/zenodo-files/")

    def test_a_visitor_sees_the_files_of_the_record(self):
        with mock.patch(
            "mousetube_api.utils.zenodo_files.requests.get",
            return_value=FakeAnswer(self.record),
        ) as get:
            response = self.get()
            self.get()  # kept: Zenodo is asked once
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(response.data["record"], "https://zenodo.org/records/111")
        self.assertEqual(
            [f["name"] for f in response.data["files"]], ["a b.wav", "a b_usvseg.csv"]
        )
        self.assertEqual(
            response.data["files"][0]["url"],
            "https://zenodo.org/records/111/files/a%20b.wav?download=1",
        )

    def test_a_file_that_zenodo_does_not_hold_has_no_list(self):
        other = self.file("c.wav", "https://genetics.wustl.edu/x/c.wav")
        with mock.patch("mousetube_api.utils.zenodo_files.requests.get") as get:
            self.assertEqual(self.get(other).status_code, 404)
        get.assert_not_called()

    def test_a_file_nobody_may_see_has_no_list(self):
        hidden = self.file(
            "d.wav", ZENODO.format("d.wav"), session=self.session_of("draft", "S2")
        )
        with mock.patch("mousetube_api.utils.zenodo_files.requests.get") as get:
            self.assertEqual(self.get(hidden).status_code, 404)
        get.assert_not_called()

    def test_zenodo_down_is_a_502_not_a_crash(self):
        with mock.patch(
            "mousetube_api.utils.zenodo_files.requests.get",
            side_effect=zenodo_files.requests.ConnectionError("down"),
        ):
            self.assertEqual(self.get().status_code, 502)

    def test_the_lookups_are_capped(self):
        with (
            mock.patch.object(zenodo_files, "LOOKUPS_PER_MINUTE", 0),
            mock.patch("mousetube_api.utils.zenodo_files.requests.get") as get,
        ):
            response = self.get()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "60")
        get.assert_not_called()


class DatasetZip(Base):
    """The zip of a dataset: every file of the Zenodo records of its files, one folder per record."""

    def setUp(self):
        super().setUp()
        # record 111 holds a recording and a table; record 222 too (its row links to the whole record)
        self.records = {
            "111": [("a.wav", b"AAAAAAAA"), ("a_usvseg.csv", b"CC")],
            "222": [("b c.wav", b"BBBB"), ("b c_ratrec.csv", b"DDD")],
        }
        self.a = self.file("a.wav", ZENODO.format("a.wav"))
        self.b = self.file(
            "b c.wav", "https://zenodo.org/api/records/222/files-archive"
        )
        self.elsewhere = self.file("e.wav", "https://genetics.wustl.edu/e.wav")
        self.bodies = {}  # address of a file -> what is answered instead of its content
        patcher = mock.patch(
            "mousetube_api.utils.zenodo_files.requests.get", side_effect=self._get
        )
        self.get = patcher.start()
        self.addCleanup(patcher.stop)

    def address(self, record, name):
        return zenodo_files.file_url("zenodo.org", record, name)

    def _get(self, url, **kwargs):
        for record, files in self.records.items():
            if url == f"https://zenodo.org/api/records/{record}":
                return FakeAnswer(
                    {"files": [{"key": n, "size": len(b)} for n, b in files]}
                )
            for name, body in files:
                if url == self.address(record, name):
                    return self.bodies.get(url) or FakeAnswer(body)
        raise AssertionError(f"unexpected request: {url}")

    def free(self):
        """True when no place is taken any more."""
        return not any(
            cache.get(key)
            for key in (
                f"dataset-zip:user:{self.owner.pk}",
                "dataset-zip:slot:0",
                "dataset-zip:slot:1",
            )
        )

    def post(self, user=None):
        self.client.force_authenticate(user)
        return self.client.post(self.url())

    def test_a_visitor_cannot_ask_for_the_zip(self):
        self.assertEqual(self.post(None).status_code, 401)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 403)
        self.get.assert_not_called()

    def test_a_signed_in_user_gets_every_file_of_the_records(self):
        answer = self.post(self.owner)
        self.assertEqual(answer.status_code, 200)
        self.assertEqual(
            answer.data["files"], 4
        )  # the tables too, not only the recordings
        self.assertEqual(answer.data["bytes"], 8 + 2 + 4 + 3)
        self.assertEqual(answer.data["left_out"], 1)
        self.client.force_authenticate(None)
        response, archive = self.download(token=answer.data["token"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertEqual(response["X-Accel-Buffering"], "no")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(archive.testzip(), None)
        self.assertEqual(
            sorted(archive.namelist()),
            ["a/a.wav", "a/a_usvseg.csv", "b c/b c.wav", "b c/b c_ratrec.csv"],
        )
        self.assertEqual(archive.read("a/a.wav"), b"AAAAAAAA")
        self.assertEqual(archive.read("b c/b c_ratrec.csv"), b"DDD")
        self.assertTrue(self.free())

    def test_a_record_is_only_fetched_once_when_two_files_share_it(self):
        self.file("a2.wav", ZENODO.format("a2.wav"))  # same record 111 as `a.wav`
        _, archive = self.download(self.owner)
        self.assertEqual(
            sorted(n for n in archive.namelist() if n.startswith("a")),
            ["a/a.wav", "a/a_usvseg.csv"],
        )

    def test_a_row_that_links_the_whole_record_is_fetched_by_the_files_of_the_record(
        self,
    ):
        self.download(self.owner)
        asked = [call.args[0] for call in self.get.call_args_list]
        self.assertIn(self.address("222", "b c.wav"), asked)
        self.assertNotIn("https://zenodo.org/api/records/222/files-archive", asked)

    def test_the_token_is_for_one_dataset_one_use_and_two_minutes(self):
        other = Dataset.objects.create(name="Other", created_by=self.owner)
        response, _ = self.download(token=self.token(dataset=other))
        self.assertEqual(response.status_code, 403)
        response, _ = self.download(token="not-a-token")
        self.assertEqual(response.status_code, 403)
        token = self.token()
        self.assertEqual(self.download(token=token)[0].status_code, 200)
        self.assertEqual(self.download(token=token)[0].status_code, 403)  # used once
        with mock.patch.object(views, "DATASET_ZIP_TOKEN_SECONDS", -1):
            self.assertEqual(self.download(token=self.token())[0].status_code, 403)

    def test_the_zip_holds_what_the_dataset_page_shows_to_the_user(self):
        """A draft put in a dataset is shown to the administrators only, its author included."""
        hidden = self.session_of("draft", "S2")
        self.dataset.recording_session_list.add(hidden)
        self.records["444"] = [("secret.wav", b"SECRET")]
        self.file(
            "secret.wav",
            "https://zenodo.org/records/444/files/secret.wav",
            session=hidden,
        )
        admin = get_user_model().objects.create_user(
            "adm", "adm@igbmc.fr", "x", is_staff=True
        )
        for user in (self.other, self.owner):
            _, archive = self.download(user)
            self.assertNotIn("secret/secret.wav", archive.namelist())
        _, archive = self.download(admin)
        self.assertIn("secret/secret.wav", archive.namelist())

    def test_a_file_that_fails_is_listed_and_does_not_stop_the_others(self):
        self.bodies[self.address("111", "a.wav")] = FakeAnswer(fail=True)
        _, archive = self.download(self.owner)
        self.assertNotIn("a/a.wav", archive.namelist())
        self.assertIn("a/a_usvseg.csv", archive.namelist())
        self.assertIn("b c/b c.wav", archive.namelist())
        self.assertIn("a/a.wav", archive.read("_errors.txt").decode())
        self.assertTrue(self.free())

    def test_a_file_cut_short_is_listed(self):
        self.bodies[self.address("111", "a.wav")] = FakeAnswer(b"AAAAAAAA", cut_after=4)
        _, archive = self.download(self.owner)
        self.assertIn("incomplete", archive.read("_errors.txt").decode())

    def test_one_download_at_a_time_per_user(self):
        cache.add(f"dataset-zip:user:{self.owner.pk}", 1, 60)
        response, _ = self.download(self.owner)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "120")

    @override_settings(DATASET_ZIP_PARALLEL=1)
    def test_the_server_makes_a_limited_number_of_zips_at_once(self):
        cache.add("dataset-zip:slot:0", 1, 60)
        response, _ = self.download(self.owner)
        self.assertEqual(response.status_code, 429)
        # the place of the user is given back, so the next try is not blocked by itself
        self.assertFalse(cache.get(f"dataset-zip:user:{self.owner.pk}"))

    @override_settings(DATASET_ZIP_MAX_FILES=3)
    def test_too_many_files_are_refused_before_anything_starts(self):
        self.assertEqual(self.post(self.owner).status_code, 413)

    @override_settings(DATASET_ZIP_MAX_BYTES=10)
    def test_a_dataset_too_heavy_is_refused_before_anything_starts(self):
        """The sizes come from Zenodo, so the limit works when the rows have no size."""
        self.assertEqual(self.post(self.owner).status_code, 413)

    def test_zenodo_not_answering_is_said_not_crashed(self):
        self.client.force_authenticate(self.owner)
        with mock.patch.object(
            views, "record_files", side_effect=zenodo_files.ZenodoUnavailable()
        ):
            self.assertEqual(self.client.post(self.url()).status_code, 502)

    def test_a_dataset_without_file_on_zenodo_is_a_404(self):
        File.objects.exclude(pk=self.elsewhere.pk).delete()
        self.assertEqual(self.post(self.owner).status_code, 404)

    def test_the_size_limit_stops_the_zip_and_says_so(self):
        entries = [
            ("a.wav", self.address("111", "a.wav"), 8),
            ("b c.wav", self.address("222", "b c.wav"), 4),
        ]
        body = b"".join(zenodo_files.iter_zip(entries, max_bytes=4))
        archive = zipfile.ZipFile(io.BytesIO(body))
        report = archive.read("_errors.txt").decode()
        self.assertIn("a.wav: incomplete", report)
        self.assertIn("b c.wav: not added", report)


class Stream(TestCase):
    """The place is given back whatever ends the download, the visitor leaving included."""

    def run_stream(self, chunks, stop_after=None):
        given = []

        async def go():
            stream = views._stream(iter(chunks), lambda: given.append(1))
            seen = 0
            async for _ in stream:
                seen += 1
                if stop_after and seen >= stop_after:
                    break
            await stream.aclose()

        asyncio.run(go())
        return given

    def test_given_back_at_the_end(self):
        self.assertEqual(self.run_stream([b"a", b"b"]), [1])

    def test_given_back_when_the_visitor_leaves(self):
        self.assertEqual(self.run_stream([b"a", b"b", b"c"], stop_after=1), [1])

    def test_given_back_when_the_zip_fails(self):
        def broken():
            yield b"a"
            raise RuntimeError("boom")

        given = []

        async def go():
            async for _ in views._stream(broken(), lambda: given.append(1)):
                pass

        with self.assertRaises(RuntimeError):
            asyncio.run(go())
        self.assertEqual(given, [1])


class RecordZip(Base):
    """The zip of every file of the Zenodo record a file belongs to."""

    API = "https://zenodo.org/api/records/111"
    NAMES = {"a b.wav": b"AAAAAAAA", "a b_usvseg.csv": b"CCCC"}

    def setUp(self):
        super().setUp()
        self.row = self.file("a b.wav", ZENODO.format("a%20b.wav"))
        self.record = {
            "files": [{"key": n, "size": len(b)} for n, b in self.NAMES.items()]
        }
        patcher = mock.patch(
            "mousetube_api.utils.zenodo_files.requests.get", side_effect=self._get
        )
        self.get = patcher.start()
        self.addCleanup(patcher.stop)

    def _get(self, url, **kwargs):
        if url == self.API:
            return FakeAnswer(self.record)
        for name, body in self.NAMES.items():
            if url == zenodo_files.file_url("zenodo.org", "111", name):
                return FakeAnswer(body)
        raise AssertionError(f"unexpected request: {url}")

    def url(self, file=None):
        return f"/api/file/{(file or self.row).pk}/record-download/"

    def token(self, user=None, file=None, salt="record-zip"):
        return signing.dumps(
            {"u": (user or self.owner).pk, "k": (file or self.row).pk}, salt=salt
        )

    def zip_of(self, token, file=None):
        response = self.client.get(self.url(file), {"token": token})
        if response.status_code != 200:
            return response, None
        return response, zipfile.ZipFile(io.BytesIO(b"".join(response)))

    def test_a_visitor_cannot_ask_for_it(self):
        self.assertEqual(self.client.post(self.url()).status_code, 401)
        self.assertEqual(self.client.get(self.url()).status_code, 403)

    def test_a_signed_in_user_gets_every_file_of_the_record(self):
        self.client.force_authenticate(self.owner)
        answer = self.client.post(self.url())
        self.assertEqual(answer.status_code, 200)
        self.assertEqual((answer.data["files"], answer.data["bytes"]), (2, 12))
        self.client.force_authenticate(None)
        response, archive = self.zip_of(answer.data["token"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertEqual(response["X-Accel-Buffering"], "no")
        self.assertIn("_record.zip", response["Content-Disposition"])
        self.assertEqual(archive.testzip(), None)
        self.assertEqual(sorted(archive.namelist()), sorted(self.NAMES))
        self.assertEqual(archive.read("a b_usvseg.csv"), b"CCCC")
        self.assertFalse(cache.get(f"dataset-zip:user:{self.owner.pk}"))

    def test_the_token_of_a_dataset_does_not_open_a_record(self):
        response, _ = self.zip_of(self.token(salt=views.DATASET_ZIP_SALT))
        self.assertEqual(response.status_code, 403)

    def test_the_token_is_for_one_file_and_one_use(self):
        other = self.file("z.wav", ZENODO.format("z.wav"))
        self.assertEqual(self.zip_of(self.token(file=other))[0].status_code, 403)
        token = self.token()
        self.assertEqual(self.zip_of(token)[0].status_code, 200)
        self.assertEqual(self.zip_of(token)[0].status_code, 403)

    def test_a_file_nobody_may_see_has_no_zip(self):
        hidden = self.file(
            "d.wav", ZENODO.format("d.wav"), session=self.session_of("draft", "S2")
        )
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(self.url(hidden)).status_code, 404)

    def test_a_file_that_zenodo_does_not_hold_has_no_zip(self):
        elsewhere = self.file("e.wav", "https://genetics.wustl.edu/e.wav")
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.post(self.url(elsewhere)).status_code, 404)

    def test_zenodo_down_or_busy_is_said_not_crashed(self):
        self.client.force_authenticate(self.owner)
        with mock.patch.object(
            views, "record_files", side_effect=zenodo_files.ZenodoUnavailable()
        ):
            self.assertEqual(self.client.post(self.url()).status_code, 502)
        with mock.patch.object(
            views, "record_files", side_effect=zenodo_files.ZenodoBusy()
        ):
            self.assertEqual(self.client.post(self.url()).status_code, 429)

    @override_settings(DATASET_ZIP_MAX_BYTES=10)
    def test_a_record_too_heavy_is_refused_before_anything_starts(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.post(self.url()).status_code, 413)


class FixArchiveLinks(Base):
    """The command that replaces the links to a whole record by the link of the file."""

    ARCHIVE = "https://zenodo.org/api/records/222/files-archive"
    TARGET = "mousetube_api.management.commands.fix_zenodo_archive_links.record_files"

    def run_command(self, *args, names=("b c.wav", "Rat 3.wav")):
        from django.core.management import call_command

        out = io.StringIO()
        files = [{"name": n, "size": 1, "url": ""} for n in names]
        with mock.patch(self.TARGET, return_value=files):
            call_command("fix_zenodo_archive_links", *args, stdout=out)
        return out.getvalue()

    def test_nothing_changes_without_apply(self):
        row = self.file("b c.wav", self.ARCHIVE)
        report = self.run_command()
        row.refresh_from_db()
        self.assertEqual(row.link, self.ARCHIVE)
        self.assertIn("1 to change", report)

    def test_apply_gives_the_link_of_the_file_and_leaves_the_others(self):
        archive = self.file("b c.wav", self.ARCHIVE)
        direct = self.file("a.wav", ZENODO.format("a.wav"))
        elsewhere = self.file("e.wav", "https://genetics.wustl.edu/e.wav")
        unnamed = self.file("", "https://zenodo.org/api/records/333/files-archive")
        self.run_command("--apply")
        for row in (archive, direct, elsewhere, unnamed):
            row.refresh_from_db()
        self.assertEqual(
            archive.link, "https://zenodo.org/records/222/files/b%20c.wav?download=1"
        )
        self.assertEqual(direct.link, ZENODO.format("a.wav"))
        self.assertEqual(elsewhere.link, "https://genetics.wustl.edu/e.wav")
        self.assertEqual(
            unnamed.link, "https://zenodo.org/api/records/333/files-archive"
        )
        # a second run finds nothing more to do
        self.assertIn("0 changed", self.run_command("--apply"))

    def test_the_case_of_the_name_is_the_one_of_the_record(self):
        """Zenodo tells capitals apart: `cage` in the row, `Cage` in the record."""
        row = self.file("rat 3 cage.wav", self.ARCHIVE)
        self.run_command("--apply", names=("Rat 3 Cage.wav",))
        row.refresh_from_db()
        self.assertEqual(
            row.link,
            "https://zenodo.org/records/222/files/Rat%203%20Cage.wav?download=1",
        )

    def test_a_file_that_is_not_in_the_record_is_left_alone(self):
        row = self.file("missing.wav", self.ARCHIVE)
        report = self.run_command("--apply", names=("other.wav",))
        row.refresh_from_db()
        self.assertEqual(row.link, self.ARCHIVE)
        self.assertIn("no such file in the record", report)

    def test_zenodo_not_answering_changes_nothing(self):
        from django.core.management import call_command

        row = self.file("b c.wav", self.ARCHIVE)
        out = io.StringIO()
        with mock.patch(self.TARGET, side_effect=zenodo_files.ZenodoUnavailable()):
            call_command("fix_zenodo_archive_links", "--apply", stdout=out)
        row.refresh_from_db()
        self.assertEqual(row.link, self.ARCHIVE)
        self.assertIn("Zenodo does not answer", out.getvalue())
