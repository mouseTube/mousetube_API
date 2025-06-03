# from django.core.management.base import BaseCommand
# from mousetube_api.models import (
#     RecordingSession,
#     Metadata,
#     MetadataField,
#     Protocol,
#     File,
#     MetadataCategory
# )
# from django.contrib.contenttypes.models import ContentType


# class Command(BaseCommand):
#     help = "Create or update Metadata for each RecordingSession (e.g., temperature, microphone)"

#     def handle(self, *args, **options):
#         # Get content types for the models involved
#         ct_rec = ContentType.objects.get_for_model(RecordingSession)
#         ct_pro = ContentType.objects.get_for_model(Protocol)
#         ct_file = ContentType.objects.get_for_model(File)

#         sessions = RecordingSession.objects.all()
#         count = 0  # Counter for how many metadata entries are created or updated
#         count_files = 0  # Counter for file metadata entries

#         for session in sessions:
#             # --- Temperature metadata (applied to both RecordingSession and Protocol) ---
#             if session.temperature:
#                 # Ensure temperature category exists
#                 temperature_cat_rs, _ = MetadataCategory.objects.get_or_create(
#                     name="temperature",
#                     source="recording_session"
#                 )
#                 temperature_cat_pro, _ = MetadataCategory.objects.get_or_create(
#                     name="temperature",
#                     source="protocol"
#                 )

#                 # RecordingSession-level metadata
#                 Metadata.objects.update_or_create(
#                     content_type=ct_rec,
#                     object_id=session.id,
#                     metadata_field=MetadataField.objects.get(
#                         name="value", metadata_category=temperature_cat_rs
#                     ),
#                     defaults={"value": session.temperature}
#                 )
#                 count += 1

#                 Metadata.objects.update_or_create(
#                     content_type=ct_rec,
#                     object_id=session.id,
#                     metadata_field=MetadataField.objects.get(
#                         name="unit", metadata_category=temperature_cat_rs
#                     ),
#                     defaults={"value": "°C"}
#                 )
#                 count += 1

#                 # Protocol-level metadata
#                 Metadata.objects.update_or_create(
#                     content_type=ct_pro,
#                     object_id=session.protocol.id,
#                     metadata_field=MetadataField.objects.get(
#                         name="value", metadata_category=temperature_cat_pro
#                     ),
#                     defaults={"value": session.temperature}
#                 )
#                 count += 1

#                 Metadata.objects.update_or_create(
#                     content_type=ct_pro,
#                     object_id=session.protocol.id,
#                     metadata_field=MetadataField.objects.get(
#                         name="unit", metadata_category=temperature_cat_pro
#                     ),
#                     defaults={"value": "°C"}
#                 )
#                 count += 1

#             # --- Protocol level light-cycle metadata ---
#             if session.light_cycle:
#                 Metadata.objects.update_or_create(
#                     content_type=ct_pro,
#                     object_id=session.protocol.id,
#                     metadata_field=MetadataField.objects.get(
#                         name="light_cycle", source="protocol"
#                     ),
#                     defaults={"value": session.light_cycle},
#                 )
#                 count += 1

#             # --- Microphone metadata ---
#             if session.microphone:
#                 Metadata.objects.update_or_create(
#                     content_type=ct_rec,
#                     object_id=session.id,
#                     metadata_field=MetadataField.objects.get(
#                         name="microphone", source="recording_session"
#                     ),
#                     defaults={"value": session.microphone},
#                 )
#                 count += 1

#             # --- Acquisition hardware metadata ---
#             if session.acquisition_hardware:
#                 Metadata.objects.update_or_create(
#                     content_type=ct_rec,
#                     object_id=session.id,
#                     metadata_field=MetadataField.objects.get(
#                         name="acquisition_hardware", source="recording_session"
#                     ),
#                     defaults={"value": session.acquisition_hardware},
#                 )
#                 count += 1

#             # --- Acquisition software metadata ---
#             if session.acquisition_software:
#                 Metadata.objects.update_or_create(
#                     content_type=ct_rec,
#                     object_id=session.id,
#                     metadata_field=MetadataField.objects.get(
#                         name="acquisition_software", source="recording_session"
#                     ),
#                     defaults={"value": session.acquisition_software},
#                 )
#                 count += 1

#             # --- Sampling rate metadata ---
#             if session.sampling_rate:
#                 files = File.objects.filter(recording_session=session)
#                 for file in files:
#                     Metadata.objects.update_or_create(
#                         content_type=ct_file,
#                         object_id=file.id,
#                         metadata_field=MetadataField.objects.get(
#                             name="sampling_rate", source="file"
#                         ),
#                         defaults={"value": session.sampling_rate},
#                     )
#                 count_files += 1

#             # --- Bit depth metadata ---
#             if session.bit_depth:
#                 files = File.objects.filter(recording_session=session)
#                 for file in files:
#                     Metadata.objects.update_or_create(
#                         content_type=ct_file,
#                         object_id=file.id,
#                         metadata_field=MetadataField.objects.get(
#                             name="bit_depth", source="file"
#                         ),
#                         defaults={"value": session.bit_depth},
#                     )
#                 count_files += 1

#             # --- Date metadata ---
#             if session.date:
#                 files = File.objects.filter(recording_session=session)
#                 for file in files:
#                     Metadata.objects.update_or_create(
#                         content_type=ct_file,
#                         object_id=file.id,
#                         metadata_field=MetadataField.objects.get(
#                             name="date", source="file"
#                         ),
#                         defaults={"value": session.date.isoformat()},
#                     )
#                 count += 1

#             # --- Laboratory metadata ---
#             if session.laboratory:
#                 Metadata.objects.update_or_create(
#                     content_type=ct_rec,
#                     object_id=session.id,
#                     metadata_field=MetadataField.objects.get(
#                         name="laboratory", source="recording_session"
#                     ),
#                     defaults={"value": session.laboratory},
#                 )
#                 count += 1

#         # --- File metadata --- #
#         for file in File.objects.all():
#             if file.name:
#                 Metadata.objects.update_or_create(
#                     content_type=ct_file,
#                     object_id=file.id,
#                     metadata_field=MetadataField.objects.get(
#                         name="filename", source="file"
#                     ),
#                     defaults={"value": file.name},
#                 )
#             count_files += 1
#         self.stdout.write(
#             self.style.SUCCESS(
#                 f"{count_files} metadata entries created/updated for Files."
#             )
#         )

#         self.stdout.write(
#             self.style.SUCCESS(
#                 f"{count} metadata entries created/updated for RecordingSession."
#             )
#         )
