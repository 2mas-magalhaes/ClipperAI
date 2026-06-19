import os
import tempfile
import unittest

import database as db
import modulo3_edicao as ed


class LayoutOptionTests(unittest.TestCase):
    def test_queue_item_stores_satisfying_flag(self):
        original_path = db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = os.path.join(tmp, "clipai_db.json")
            item = db.add_to_queue(
                "https://example.com/video",
                title="Demo",
                usar_video_satisfatorio=False,
            )
            try:
                self.assertFalse(item["usar_video_satisfatorio"])
                self.assertFalse(db.get_queue()[0]["usar_video_satisfatorio"])
                self.assertTrue(db.get_settings()["usar_video_satisfatorio"])
            finally:
                db.DB_PATH = original_path

    def test_fullscreen_layout_does_not_lookup_satisfying_video_when_disabled(self):
        calls = {}
        original_find = ed._encontrar_video_satisfatorio
        original_fps = ed.obter_fps_video
        original_encode = ed._encode_com_filtros

        def fail_find():
            raise AssertionError("_encontrar_video_satisfatorio should not be called")

        def fake_encode(caminho_video, caminho_saida, vf=None, filter_complex=None, duracao_clip=None):
            calls["filter_complex"] = filter_complex
            return True

        ed._encontrar_video_satisfatorio = fail_find
        ed.obter_fps_video = lambda _: 30
        ed._encode_com_filtros = fake_encode
        try:
            ok = ed._aplicar_edicao_standard(
                "input.mp4",
                None,
                "output.mp4",
                12,
                1920,
                1080,
                usar_video_satisfatorio=False,
            )
            self.assertTrue(ok)
            self.assertIn("scale=1080:1920", calls["filter_complex"])
        finally:
            ed._encontrar_video_satisfatorio = original_find
            ed.obter_fps_video = original_fps
            ed._encode_com_filtros = original_encode

    def test_split_layout_uses_satisfying_video_when_enabled(self):
        calls = {}
        original_find = ed._encontrar_video_satisfatorio
        original_fps = ed.obter_fps_video
        original_duration = ed._obter_duracao_video
        original_encode_2in = ed._encode_com_filtros_2in

        def fake_encode_2in(caminho_video, caminho_video2, caminho_saida, filter_complex, duracao):
            calls["video2"] = caminho_video2
            calls["filter_complex"] = filter_complex
            return True

        ed._encontrar_video_satisfatorio = lambda: "sat.mp4"
        ed.obter_fps_video = lambda _: 30
        ed._obter_duracao_video = lambda _: 120
        ed._encode_com_filtros_2in = fake_encode_2in
        try:
            ok = ed._aplicar_edicao_standard(
                "input.mp4",
                None,
                "output.mp4",
                12,
                1920,
                1080,
                usar_video_satisfatorio=True,
            )
            self.assertTrue(ok)
            self.assertEqual("sat.mp4", calls["video2"])
            self.assertIn("vstack=inputs=2", calls["filter_complex"])
        finally:
            ed._encontrar_video_satisfatorio = original_find
            ed.obter_fps_video = original_fps
            ed._obter_duracao_video = original_duration
            ed._encode_com_filtros_2in = original_encode_2in


if __name__ == "__main__":
    unittest.main()
