import json
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

from services.click_element_capture_service import (
    REGION_VIEW_NODE_ID,
    SHELTER_VIEW_NODE_ID,
    UNKNOWN_VIEW_NODE_ID,
    build_recorded_click_element_name,
    capture_clicked_element_crop,
    classify_horizontal_band_from_bottom,
    classify_doomsday_view,
    is_empty_space_popup_dismissal_band,
    register_recorded_click_element,
)


class ClickElementCaptureServiceTests(unittest.TestCase):
    def test_capture_clicked_element_crop_trims_to_probable_button_contour(self):
        context = Image.new("RGB", (224, 224), color=(20, 20, 20))
        draw = ImageDraw.Draw(context)
        draw.rounded_rectangle((62, 74, 166, 132), radius=8, fill=(55, 90, 170), outline=(220, 230, 255), width=3)

        with patch(
            "services.click_element_capture_service._capture_rect_image",
            return_value=context,
        ):
            crop = capture_clicked_element_crop(abs_x=512, abs_y=412, window_rect=(400, 300, 900, 800))

        self.assertLess(crop.image.size[0], 160)
        self.assertLess(crop.image.size[1], 110)
        self.assertGreaterEqual(crop.contour_confidence, 0.8)
        self.assertTrue(crop.crop_bounds[0] <= 512 <= crop.crop_bounds[2])
        self.assertTrue(crop.crop_bounds[1] <= 412 <= crop.crop_bounds[3])

    def test_capture_clicked_element_crop_can_follow_wide_text_controls(self):
        context = Image.new("RGB", (320, 192), color=(18, 18, 18))
        draw = ImageDraw.Draw(context)
        draw.rectangle((72, 70, 250, 108), fill=(70, 110, 190), outline=(230, 235, 255), width=2)
        draw.line((88, 88, 230, 88), fill=(245, 245, 245), width=4)

        with patch(
            "services.click_element_capture_service._capture_rect_image",
            return_value=context,
        ):
            crop = capture_clicked_element_crop(abs_x=512, abs_y=412, window_rect=(352, 316, 800, 700))

        self.assertGreater(crop.image.size[0], crop.image.size[1] * 2)
        self.assertGreaterEqual(crop.contour_confidence, 0.8)

    def test_classify_doomsday_view_from_bottom_left_switch_icon(self):
        shelter_result = Mock(found=True, matched_element_name="region_view_switch_globe_icon")
        region_result = Mock(found=True, matched_element_name="shelter_view_switch_home_icon")
        unknown_result = Mock(found=False, matched_element_name=None)

        with patch("services.click_element_capture_service.search_game_window_elements", return_value=shelter_result):
            self.assertEqual(classify_doomsday_view((0, 0, 100, 100)), SHELTER_VIEW_NODE_ID)

        with patch("services.click_element_capture_service.search_game_window_elements", return_value=region_result):
            self.assertEqual(classify_doomsday_view((0, 0, 100, 100)), REGION_VIEW_NODE_ID)

        with patch("services.click_element_capture_service.search_game_window_elements", return_value=unknown_result):
            self.assertEqual(classify_doomsday_view((0, 0, 100, 100)), UNKNOWN_VIEW_NODE_ID)

    def test_register_recorded_click_element_saves_png_with_graph_metadata(self):
        context = Image.new("RGB", (224, 224), color=(18, 18, 18))
        draw = ImageDraw.Draw(context)
        draw.rectangle((72, 84, 154, 138), fill=(80, 120, 210), outline=(240, 240, 255), width=3)
        view_result = Mock(found=True, matched_element_name="region_view_switch_globe_icon")

        captured = {}

        def fake_create_game_element(nome, descrizione, immagine_blob, formato_immagine):
            captured["nome"] = nome
            captured["descrizione"] = descrizione
            captured["blob"] = immagine_blob
            captured["format"] = formato_immagine
            return 42

        with (
            patch("services.click_element_capture_service.search_game_window_elements", return_value=view_result),
            patch("services.click_element_capture_service.get_all_game_elements", return_value=[]),
            patch("services.click_element_capture_service.create_game_element", side_effect=fake_create_game_element),
        ):
            observation = register_recorded_click_element(
                macro_name="Apri Eroi",
                event_time_ms=1234,
                button="left",
                abs_x=512,
                abs_y=412,
                normalized_x=0.25,
                normalized_y=0.75,
                window_rect=(400, 300, 900, 800),
            )

        self.assertEqual(observation.element_id, 42)
        self.assertEqual(observation.view_node_id, SHELTER_VIEW_NODE_ID)
        self.assertEqual(captured["format"], "PNG")
        self.assertGreater(len(captured["blob"]), 100)
        self.assertTrue(captured["nome"].startswith("recorded_click_apri_eroi_001234ms_"))

        metadata_json = captured["descrizione"].split("AUTO_CLICK_ELEMENT_METADATA:", 1)[1]
        metadata = json.loads(metadata_json)
        self.assertEqual(metadata["graph_id"], "doomsday-default-ui-graph")
        self.assertEqual(metadata["view_node_id"], SHELTER_VIEW_NODE_ID)
        self.assertEqual(metadata["macro_name"], "Apri Eroi")
        self.assertEqual(metadata["normalized_position"]["x"], 0.25)

    def test_register_recorded_click_element_uses_preclassified_view_when_available(self):
        context = Image.new("RGB", (224, 224), color=(18, 18, 18))

        with (
            patch("services.click_element_capture_service.search_game_window_elements") as classify,
            patch("services.click_element_capture_service.get_all_game_elements", return_value=[]),
            patch("services.click_element_capture_service.create_game_element", return_value=9),
        ):
            observation = register_recorded_click_element(
                macro_name="Apri Eroi",
                event_time_ms=1234,
                button="left",
                abs_x=512,
                abs_y=412,
                normalized_x=0.25,
                normalized_y=0.75,
                window_rect=(400, 300, 900, 800),
                view_node_id="shelter_interior_view",
                sequence_index=3,
                previous_element_id=8,
            )

        self.assertEqual(observation.view_node_id, "shelter_interior_view")
        classify.assert_not_called()
        self.assertFalse(observation.reused_existing)

    def test_register_recorded_click_element_reuses_existing_catalog_element(self):
        crop_image = Image.new("RGB", (92, 54), color=(80, 120, 210))
        metadata_description = (
            "Elemento acquisito automaticamente durante la registrazione macro.\n"
            "[semantic_hint] old_hint\n"
            "AUTO_CLICK_ELEMENT_METADATA:{\"macro_name\":\"Macro precedente\"}"
        )
        existing_element = {
            "id": 7,
            "nome": "recorded_click_existing",
            "descrizione": metadata_description,
            "immagine": crop_image.tobytes(),
            "formato_immagine": "PNG",
        }
        view_result = Mock(found=True, matched_element_name="region_view_switch_globe_icon")
        updated = {}

        def fake_blob_to_image(_blob, _fmt):
            return crop_image.copy()

        def fake_update(element_id, **kwargs):
            updated["id"] = element_id
            updated.update(kwargs)
            return True

        with (
            patch("services.click_element_capture_service.search_game_window_elements", return_value=view_result),
            patch(
                "services.click_element_capture_service.capture_clicked_element_crop",
                return_value=type(
                    "Crop",
                    (),
                    {
                        "image": crop_image.copy(),
                        "capture_bounds": (10, 20, 120, 140),
                        "crop_bounds": (20, 30, 112, 84),
                        "click_offset_in_crop": (25, 20),
                        "contour_confidence": 0.91,
                    },
                )(),
            ),
            patch("services.click_element_capture_service.get_all_game_elements", return_value=[existing_element]),
            patch("services.click_element_capture_service.blob_to_image", side_effect=fake_blob_to_image),
            patch("services.click_element_capture_service.update_game_element", side_effect=fake_update),
            patch("services.click_element_capture_service.create_game_element") as create_game_element,
        ):
            observation = register_recorded_click_element(
                macro_name="Apri Eroi",
                event_time_ms=1234,
                button="left",
                abs_x=512,
                abs_y=412,
                normalized_x=0.25,
                normalized_y=0.75,
                window_rect=(400, 300, 900, 800),
            )

        self.assertEqual(observation.element_id, 7)
        self.assertEqual(observation.element_name, "recorded_click_existing")
        self.assertTrue(observation.reused_existing)
        create_game_element.assert_not_called()
        self.assertEqual(updated["id"], 7)
        self.assertIn("AUTO_CLICK_ELEMENT_METADATA:", updated["descrizione"])
        self.assertIn("Apri Eroi", updated["descrizione"])

    def test_recorded_click_element_name_is_stable_and_slugged(self):
        name = build_recorded_click_element_name(
            macro_name="Macro: Apri Campagna!",
            event_time_ms=77,
            abs_x=10,
            abs_y=20,
        )

        self.assertEqual(name, "recorded_click_macro_apri_campagna_000077ms_10x20")

    def test_horizontal_bands_are_counted_from_bottom_for_empty_space_popup_dismissal(self):
        self.assertEqual(classify_horizontal_band_from_bottom(0.85), 1)
        self.assertEqual(classify_horizontal_band_from_bottom(0.65), 2)
        self.assertEqual(classify_horizontal_band_from_bottom(0.45), 3)
        self.assertEqual(classify_horizontal_band_from_bottom(0.25), 4)
        self.assertEqual(classify_horizontal_band_from_bottom(0.05), 5)
        self.assertTrue(is_empty_space_popup_dismissal_band(0.25))
        self.assertFalse(is_empty_space_popup_dismissal_band(0.85))


if __name__ == "__main__":
    unittest.main()
