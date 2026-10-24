import base64
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from PIL import Image, PngImagePlugin
from cleanliness import InvalidPhoto, ReviewUnavailable, encode_photo, review_photo


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent, prefix=".tmp-")
        self.addCleanup(self.temp.cleanup)
        self.photo = Path(self.temp.name) / "photo.png"
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("private_location", "do not send this metadata")
        Image.new("RGBA", (1600, 800), (255, 255, 255, 128)).save(self.photo, pnginfo=metadata)

    def review(self, **kwargs):
        return review_photo(self.photo, "Wash the dishes", base_url="http://127.0.0.1:11434",
                            model="qwen3-vl:4b-instruct", **kwargs)

    def test_photo_is_resized_reencoded_and_stripped_of_metadata(self):
        raw = base64.b64decode(encode_photo(self.photo))
        self.assertNotIn(b"private_location", raw)
        with Image.open(BytesIO(raw)) as photo:
            self.assertEqual(photo.format, "JPEG")
            self.assertEqual(photo.size, (1024, 512))
            self.assertEqual(photo.mode, "RGB")
            self.assertFalse(photo.getexif())

    def test_invalid_or_tiny_photo_is_rejected_before_inference(self):
        self.photo.write_bytes(b"not actually an image")
        with self.assertRaises(InvalidPhoto):
            encode_photo(self.photo)
        Image.new("RGB", (10, 10)).save(self.photo)
        with self.assertRaises(InvalidPhoto):
            encode_photo(self.photo)

    def test_local_model_receives_image_chore_and_structured_schema(self):
        result = {"verdict": "clean", "reason": "The dishes and sink look clean.", "issues": []}
        with patch("cleanliness.open_local") as transport:
            transport.return_value.__enter__.return_value.read.return_value = json.dumps({"done": True, "response": json.dumps(result)}).encode()
            actual = self.review(timeout=30)
        self.assertEqual(actual["verdict"], "clean")
        self.assertEqual(actual["model"], "qwen3-vl:4b-instruct")
        args, kwargs = transport.call_args
        request = args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/generate")
        self.assertEqual(kwargs["timeout"], 30)
        self.assertIn("Wash the dishes", payload["prompt"])
        self.assertEqual(len(payload["images"]), 1)
        self.assertEqual(payload["format"]["properties"]["verdict"]["enum"], ["clean", "needs_work", "unclear"])
        self.assertFalse(payload["stream"])

    def test_invalid_model_responses_never_approve_a_photo(self):
        responses = [
            b"not json", json.dumps({"done": False, "response": "{}"}).encode(),
            json.dumps({"done": True, "response": '{"verdict":"clean"}'}).encode(),
            json.dumps({"done": True, "response": json.dumps({"verdict":"clean", "reason":"", "issues":[]})}).encode(),
            json.dumps({"done": True, "response": json.dumps({"verdict":"approved", "reason":"okay", "issues":[]})}).encode(),
            json.dumps({"done": True, "response": json.dumps({"verdict":"clean", "reason":"okay", "issues":"none"})}).encode(),
        ]
        for response in responses:
            with self.subTest(response=response), patch("cleanliness.open_local") as transport:
                transport.return_value.__enter__.return_value.read.return_value = response
                with self.assertRaises(ReviewUnavailable):
                    self.review()

    def test_missing_model_offline_and_timeout_return_actionable_errors(self):
        for error in (HTTPError("local", 404, "missing", None, None), URLError("offline"), TimeoutError()):
            with self.subTest(error=error), patch("cleanliness.open_local", side_effect=error):
                with self.assertRaisesRegex(ReviewUnavailable, "[Oo]llama|ollama pull"):
                    self.review()

    def test_remote_model_addresses_are_not_allowed(self):
        with patch("cleanliness.open_local") as transport:
            with self.assertRaises(ReviewUnavailable):
                review_photo(self.photo, "Dishes", base_url="http://external.example.com", model="test")
            transport.assert_not_called()


if __name__ == "__main__":
    unittest.main()
