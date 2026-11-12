"""
Created by Nicolas Torquet at 27/10/2023
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django_countries.serializer_fields import CountryField
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from mousetube_api.utils.email_domains import is_personal_email
from mousetube_api.utils.moderation import (
    SESSION_LOCKED,
    VALIDATED,
    WAITING,
    notify_admin_review,
    session_pending_entries,
)
from mousetube_api.utils.ontologies import (
    OntologyError,
    get_or_create_term,
    sex_term,
)
from mousetube_api.utils.orcid_proof import read_orcid_proof
from mousetube_api.utils.registration import email_is_verified
from mousetube_api.utils.validators import (
    validate_doi,
    validate_doi_link_consistency,
    validate_url,
)

from .models import (
    AnimalProfile,
    Contact,
    Dataset,
    Favorite,
    File,
    Hardware,
    Laboratory,
    OntologyTerm,
    PageView,
    Protocol,
    RecordingSession,
    Reference,
    Repository,
    Software,
    SoftwareVersion,
    Species,
    Strain,
    Study,
    Subject,
    UserProfile,
)


class ModerationMixin:
    """Moderation of a catalog entry: draft -> waiting validation -> validated.

    The owner moves it between draft and "waiting validation" (submit / withdraw);
    only an administrator validates. The administrator is told when something is submitted.
    """

    def validate_status(self, value):
        request = self.context.get("request")
        if value == VALIDATED and not (request and request.user.is_staff):
            raise serializers.ValidationError("Only administrators can validate.")
        return value

    def save(self, **kwargs):
        # save() rather than create()/update(): several serializers define their own
        before = self.instance.status if self.instance is not None else None
        instance = super().save(**kwargs)
        if instance.status == WAITING and before != WAITING:
            notify_admin_review(instance)
        return instance


class OntologyTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = OntologyTerm
        fields = ("curie", "label", "ontology", "iri")


class OntologyTermField(serializers.Field):
    """A term of a vocabulary: written as {"curie": "PATO:0000384"} (or the bare identifier),
    read as {curie, label, ontology, iri}. The term is checked at its source."""

    def __init__(self, vocabulary, **kwargs):
        self.vocabulary = vocabulary
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_null", True)
        super().__init__(**kwargs)

    def to_representation(self, value):
        return OntologyTermSerializer(value).data

    def to_internal_value(self, data):
        curie = data.get("curie") if isinstance(data, dict) else data
        try:
            return get_or_create_term(self.vocabulary, str(curie or "").strip())
        except OntologyError as exc:
            raise serializers.ValidationError(str(exc)) from None


class OntologyTermsField(OntologyTermField):
    """A list of terms of one vocabulary."""

    def to_representation(self, value):
        return [OntologyTermSerializer(term).data for term in value.all()]

    def to_internal_value(self, data):
        if not isinstance(data, list):
            raise serializers.ValidationError("A list of terms is expected.")
        return [
            super(OntologyTermsField, self).to_internal_value(item) for item in data
        ]


class PendingAwareTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login that tells the owner of a pending account where the request stands.

    The state is only revealed when the password is correct, so it does not tell anyone
    which usernames exist. Exactly one extra password hash is computed in every failing
    case, so the response time does not give it away either.
    """

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except AuthenticationFailed:
            user_model = get_user_model()
            username = attrs.get(self.username_field)
            user = user_model.objects.filter(**{self.username_field: username}).first()
            password = attrs.get("password", "")
            if user is not None and not user.is_active:
                password_ok = user.check_password(password)
            else:
                user_model().set_password(password)  # same cost, result ignored
                password_ok = False
            if password_ok:
                state = (
                    "awaiting_review"
                    if email_is_verified(user)
                    else "awaiting_email_confirmation"
                )
                raise AuthenticationFailed(
                    {
                        "detail": "Your account is not active yet.",
                        "account_status": state,
                    }
                ) from None
            raise


class CustomUserCreateSerializer(BaseUserCreateSerializer):
    orcid_proof = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )

    class Meta(BaseUserCreateSerializer.Meta):
        fields = (
            "id",
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "orcid_proof",
        )

    def validate_email(self, value):
        if settings.REQUIRE_INSTITUTIONAL_EMAIL and is_personal_email(value):
            raise serializers.ValidationError(
                "Please use your institutional email address (university, research "
                "institute, hospital...). Personal addresses such as Gmail, Outlook, "
                "Yahoo or iCloud are not accepted."
            )
        return value

    def validate(self, attrs):
        proof = attrs.pop("orcid_proof", None)
        orcid = None
        if proof:
            try:
                orcid = read_orcid_proof(proof)
            except signing.BadSignature:
                raise serializers.ValidationError(
                    {"orcid_proof": "Invalid or expired ORCID proof."}
                ) from None
            if UserProfile.objects.filter(orcid=orcid).exists():
                raise serializers.ValidationError(
                    {"orcid_proof": "This ORCID is already linked to another user."}
                )
        attrs = super().validate(attrs)
        self._orcid = orcid
        return attrs

    def create(self, validated_data):
        user = super().create(validated_data)

        # -----------------------------
        # ⚡ Deactivate user accounts
        # -----------------------------
        user.is_active = False
        user.save()

        orcid = getattr(self, "_orcid", None)
        if orcid:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.orcid = orcid
            profile.save()

        return user


class RepositorySerializer(serializers.ModelSerializer):
    area = serializers.CharField(source="area.name")

    class Meta:
        model = Repository
        fields = "__all__"
        read_only_fields = ("created_by",)  # set by the server, never by the client


class ReferenceSerializer(ModerationMixin, serializers.ModelSerializer):
    class Meta:
        model = Reference
        fields = "__all__"
        read_only_fields = ("created_by",)  # set by the server, never by the client

    def validate_doi(self, value):
        return validate_doi(value)

    def validate_url(self, value):
        return validate_url(value)


class LaboratorySerializer(ModerationMixin, serializers.ModelSerializer):
    country = CountryField()
    organization = OntologyTermField("organization")

    class Meta:
        model = Laboratory
        fields = "__all__"
        read_only_fields = ("created_by",)  # set by the server, never by the client


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "is_staff"]
        # This serializer also answers PATCH /auth/users/me/: a user changes his own
        # name, nothing else. The role above all: it used to be writable, so anybody could
        # make himself an administrator. The e-mail needs a confirmation (not built yet).
        read_only_fields = ["id", "username", "email", "is_staff"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # The name of an author is public (it is shown on his recordings). His e-mail is
        # hidden unless he chose to show it; his role is only for him and the administrators.
        request = self.context.get("request")
        viewer = getattr(request, "user", None)
        private_ok = bool(
            viewer
            and viewer.is_authenticated
            and (viewer.is_staff or viewer.pk == instance.pk)
        )
        if not private_ok:
            data.pop("is_staff", None)
            profile = getattr(instance, "user_profile", None)
            if not (profile and profile.email_public):
                data.pop("email", None)
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(read_only=True)
    laboratory = LaboratorySerializer(read_only=True)
    laboratory_id = serializers.PrimaryKeyRelatedField(
        queryset=Laboratory.objects.all(),
        source="laboratory",
        write_only=True,
        required=False,
    )
    country = CountryField()

    class Meta:
        model = UserProfile
        fields = "__all__"
        read_only_fields = (
            "orcid",
            "created_by",
            "administrator",
        )  # orcid: verified flow only; created_by, administrator: the server


class ContactSerializer(ModerationMixin, serializers.ModelSerializer):
    country = CountryField()

    class Meta:
        model = Contact
        fields = "__all__"
        read_only_fields = ("created_by",)  # set by the server, never by the client

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if not (request and request.user.is_authenticated):
            data.pop("email", None)
        return data


class HardwareSerializer(ModerationMixin, serializers.ModelSerializer):
    references = ReferenceSerializer(many=True, read_only=True)

    references_ids = serializers.PrimaryKeyRelatedField(
        queryset=Reference.objects.all(),
        source="references",
        many=True,
        write_only=True,
        required=False,
    )

    class Meta:
        model = Hardware
        fields = "__all__"
        read_only_fields = ("created_by",)  # set by the server, never by the client

    def create(self, validated_data):
        references_data = validated_data.pop("references", [])
        users_data = validated_data.pop("users", [])
        hardware = Hardware.objects.create(**validated_data)

        # assign references
        if references_data:
            hardware.references.set(references_data)

        # assign users
        if users_data:
            user_ids = [user["id"] for user in users_data if "id" in user]
            hardware.users.set(user_ids)

        return hardware

    def update(self, instance, validated_data):
        references_data = validated_data.pop("references", None)
        users_data = validated_data.pop("users", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if references_data is not None:
            instance.references.set(references_data)

        if users_data is not None:
            user_ids = [user["id"] for user in users_data if "id" in user]
            if user_ids:
                instance.users.set(user_ids)

        return instance


class SoftwareSerializer(ModerationMixin, serializers.ModelSerializer):
    references = ReferenceSerializer(many=True, read_only=True)
    contacts = ContactSerializer(many=True, read_only=True)

    references_ids = serializers.PrimaryKeyRelatedField(
        queryset=Reference.objects.all(),
        source="references",
        many=True,
        write_only=True,
        required=False,
    )
    contacts_ids = serializers.PrimaryKeyRelatedField(
        queryset=Contact.objects.all(),
        source="contacts",
        many=True,
        write_only=True,
        required=False,
    )

    linked_sessions_count = serializers.IntegerField(read_only=True)
    linked_sessions_from_other_users = serializers.IntegerField(read_only=True)

    class Meta:
        model = Software
        fields = "__all__"
        read_only_fields = [
            "created_at",
            "modified_at",
            "created_by",
            "linked_sessions_count",
            "linked_sessions_from_other_users",
        ]

    @staticmethod
    def annotate_queryset(queryset, user=None, detail=False):
        """
        Annotate linked session counts uniquement si detail=True
        """
        if detail:
            # for a visitor, every linked session belongs to "other users"
            others = (
                ~Q(versions__recording_sessions_as_software__created_by=user)
                if user is not None and user.is_authenticated
                else None
            )
            queryset = queryset.annotate(
                linked_sessions_count=Count(
                    "versions__recording_sessions_as_software", distinct=True
                ),
                linked_sessions_from_other_users=Count(
                    "versions__recording_sessions_as_software",
                    filter=others,
                    distinct=True,
                ),
            )
        return queryset

    def create(self, validated_data):
        references_data = validated_data.pop("references", [])
        contacts_data = validated_data.pop("contacts", [])
        users_data = validated_data.pop("users", [])

        software = Software.objects.create(**validated_data)

        # ✅ assign existing references
        if references_data:
            software.references.set(references_data)

        # ✅ assign existing contacts
        if contacts_data:
            software.contacts.set(contacts_data)

        # ✅ assign existing users
        if users_data:
            user_ids = [user["id"] for user in users_data if "id" in user]
            software.users.set(user_ids)

        return software

    def update(self, instance, validated_data):
        references_data = validated_data.pop("references", None)
        contacts_data = validated_data.pop("contacts", None)
        users_data = validated_data.pop("users", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # ✅ update references if provided
        if references_data is not None:
            instance.references.set(references_data)

        # ✅ update contacts if provided
        if contacts_data is not None:
            instance.contacts.set(contacts_data)

        # ✅ update users if provided
        if users_data is not None:
            user_ids = [user["id"] for user in users_data if "id" in user]
            instance.users.set(user_ids)

        instance.save()
        return instance


class SpeciesSerializer(ModerationMixin, serializers.ModelSerializer):
    ontology_term = OntologyTermField("species")

    class Meta:
        model = Species
        fields = "__all__"
        read_only_fields = ("created_by",)  # set by the server, never by the client


class ProtocolSerializer(ModerationMixin, serializers.ModelSerializer):
    class Meta:
        model = Protocol
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "modified_at")


class SoftwareVersionSerializer(ModerationMixin, serializers.ModelSerializer):
    software = SoftwareSerializer(read_only=True)
    software_id = serializers.PrimaryKeyRelatedField(
        source="software",
        queryset=Software.objects.all(),
        write_only=True,
    )
    software_name = serializers.CharField(source="software.name", read_only=True)

    linked_sessions_count = serializers.IntegerField(read_only=True)
    linked_sessions_from_other_users = serializers.IntegerField(read_only=True)

    class Meta:
        model = SoftwareVersion
        fields = [
            "id",
            "software",
            "software_id",
            "software_name",
            "version",
            "release_date",
            "created_at",
            "modified_at",
            "created_by",
            "linked_sessions_count",
            "linked_sessions_from_other_users",
        ]
        read_only_fields = [
            "created_at",
            "modified_at",
            "created_by",
            "linked_sessions_count",
            "linked_sessions_from_other_users",
        ]


class StrainSerializer(ModerationMixin, serializers.ModelSerializer):
    species = SpeciesSerializer(read_only=True)  # lecture complète
    species_id = serializers.PrimaryKeyRelatedField(
        queryset=Species.objects.all(), write_only=True, source="species"
    )

    class Meta:
        model = Strain
        fields = "__all__"
        read_only_fields = ("created_by",)  # set by the server, never by the client

    def create(self, validated_data):
        return Strain.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# class StrainSerializer(serializers.ModelSerializer):
#     species = SpeciesSerializer()

#     class Meta:
#         model = Strain
#         fields = "__all__"

#     def create(self, validated_data):
#         species_data = validated_data.pop("species")
#         species = Species.objects.create(**species_data)
#         strain = Strain.objects.create(species=species, **validated_data)
#         return strain

#     def update(self, instance, validated_data):
#         species_data = validated_data.pop("species", None)
#         if species_data:
#             species = instance.species
#             for attr, value in species_data.items():
#                 setattr(species, attr, value)
#             species.save()
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()
#         return instance


# class AnimalProfileWriteSerializer(serializers.ModelSerializer):
#     strain = serializers.PrimaryKeyRelatedField(queryset=Strain.objects.all())

#     class Meta:
#         model = AnimalProfile
#         fields = "__all__"


# class AnimalProfileReadSerializer(serializers.ModelSerializer):
#     strain = StrainReadSerializer()

#     class Meta:
#         model = AnimalProfile
#         fields = "__all__"


class AnimalProfileSerializer(ModerationMixin, serializers.ModelSerializer):
    strain = StrainSerializer(read_only=True)
    strain_id = serializers.PrimaryKeyRelatedField(
        queryset=Strain.objects.all(), write_only=True, source="strain"
    )
    sex_term = OntologyTermField("sex")
    age_term = OntologyTermField("age")
    treatment_term = OntologyTermField("treatment")

    class Meta:
        model = AnimalProfile
        fields = "__all__"
        read_only_fields = ("created_by",)  # set by the server, never by the client

    def validate(self, data):
        # "male" / "female" are enough to know the PATO term: no need to ask for it
        sex = data.get("sex")
        if sex and not data.get("sex_term") and "sex_term" not in data:
            data["sex_term"] = sex_term(sex)
        return data


# class AnimalProfileSerializer(serializers.ModelSerializer):
#     strain = StrainSerializer()

#     class Meta:
#         model = AnimalProfile
#         fields = "__all__"

#     def create(self, validated_data):
#         strain_data = validated_data.pop("strain")
#         strain = StrainSerializer.create(StrainSerializer(), validated_data=strain_data)
#         animal_profile = AnimalProfile.objects.create(strain=strain, **validated_data)
#         return animal_profile

#     def update(self, instance, validated_data):
#         strain_data = validated_data.pop("strain", None)
#         if strain_data:
#             strain_serializer = StrainSerializer(instance.strain, data=strain_data)
#             if strain_serializer.is_valid():
#                 strain_serializer.save()
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()
#         return instance


# class SubjectSerializer(serializers.ModelSerializer):
#     user = LegacyUserSerializer(read_only=True)
#     strain = StrainSerializer(read_only=True)
#     animal_profile = AnimalProfileSerializer()

#     class Meta:
#         model = Subject
#         fields = "__all__"

#     def update(self, instance, validated_data):
#         animal_profile_data = validated_data.pop("animal_profile", None)

#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()

#         if animal_profile_data:
#             animal_profile = instance.animal_profile

#             if animal_profile:
#                 for attr, value in animal_profile_data.items():
#                     setattr(animal_profile, attr, value)
#                 animal_profile.save()
#             else:
#                 new_animal_profile = AnimalProfile.objects.create(**animal_profile_data)
#                 instance.animal_profile = new_animal_profile
#                 instance.save()

#         return instance

#     def create(self, validated_data):
#         animal_profile_data = validated_data.pop("animal_profile", None)

#         subject = Subject.objects.create(**validated_data)

#         if animal_profile_data:
#             animal_profile = AnimalProfile.objects.create(**animal_profile_data)
#             subject.animal_profile = animal_profile
#             subject.save()

#         return subject


# class SubjectReadSerializer(serializers.ModelSerializer):
#     user = LegacyUserSerializer(read_only=True)
#     strain = StrainReadSerializer(read_only=True)
#     animal_profile = AnimalProfileReadSerializer()

#     class Meta:
#         model = Subject
#         fields = "__all__"


# class SubjectWriteSerializer(serializers.ModelSerializer):
#     animal_profile = AnimalProfileWriteSerializer()

#     class Meta:
#         model = Subject
#         fields = "__all__"

#     def create(self, validated_data):
#         animal_profile_data = validated_data.pop("animal_profile", None)

#         subject = Subject.objects.create(**validated_data)

#         if animal_profile_data:
#             animal_profile = AnimalProfileWriteSerializer().create(animal_profile_data)
#             subject.animal_profile = animal_profile
#             subject.save()

#         return subject

#     def update(self, instance, validated_data):
#         animal_profile_data = validated_data.pop("animal_profile", None)

#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()

#         if animal_profile_data:
#             if instance.animal_profile:
#                 serializer = AnimalProfileWriteSerializer(
#                     instance=instance.animal_profile, data=animal_profile_data, partial=True
#                 )
#                 serializer.is_valid(raise_exception=True)
#                 serializer.save()
#             else:
#                 instance.animal_profile = AnimalProfileWriteSerializer().create(animal_profile_data)
#                 instance.save()

#         return instance


# ------------------------
# Subject Serializer
# ------------------------
class SubjectSerializer(ModerationMixin, serializers.ModelSerializer):
    animal_profile = AnimalProfileSerializer()

    class Meta:
        model = Subject
        fields = "__all__"
        read_only_fields = ("created_by",)  # set by the server, never by the client

    def create(self, validated_data):
        animal_profile_data = validated_data.pop("animal_profile", None)
        subject = Subject.objects.create(**validated_data)

        if animal_profile_data:
            serializer = AnimalProfileSerializer(data=animal_profile_data)
            serializer.is_valid(raise_exception=True)
            animal_profile = serializer.save()
            subject.animal_profile = animal_profile
            subject.save()

        return subject

    def update(self, instance, validated_data):
        animal_profile_data = validated_data.pop("animal_profile", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if animal_profile_data:
            if instance.animal_profile:
                serializer = AnimalProfileSerializer(
                    instance=instance.animal_profile,
                    data=animal_profile_data,
                    partial=True,
                )
                serializer.is_valid(raise_exception=True)
                serializer.save()
            else:
                serializer = AnimalProfileSerializer(data=animal_profile_data)
                serializer.is_valid(raise_exception=True)
                instance.animal_profile = serializer.save()
                instance.save()

        return instance


class StudyShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Study
        fields = ("id", "name", "description")


def _django_errors(exc):
    """A Django ValidationError as the dict / list a DRF ValidationError expects."""
    return exc.message_dict if hasattr(exc, "error_dict") else exc.messages


class VisiblePrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """Only the objects the signed-in user may use: published ones and his own.

    Without it, anybody could attach another user's private draft (protocol, animal
    profile, hardware...) to his own session and read it in the answer.
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        user = getattr(self.context.get("request"), "user", None)
        if user is not None and user.is_staff:
            return queryset
        model = queryset.model
        names = {f.name for f in model._meta.get_fields()}
        if model is SoftwareVersion:  # a version is as public as its software
            published = Q(software__status="validated")
            own = Q(software__created_by=user)
        elif {"status", "created_by"} <= names:
            published = Q(status="validated")
            own = Q(created_by=user)
        else:
            return queryset
        if user is not None and user.is_authenticated:
            published |= own
        return queryset.filter(published)


class RecordingSessionSerializer(serializers.ModelSerializer):
    # ---- Nested serializers GET (read only) ----
    protocol = ProtocolSerializer(read_only=True)
    studies = StudyShortSerializer(many=True, read_only=True)
    laboratory = LaboratorySerializer(read_only=True)
    animal_profiles = AnimalProfileSerializer(many=True, read_only=True)
    equipment_acquisition_software = SoftwareVersionSerializer(
        many=True, read_only=True
    )
    equipment_acquisition_hardware_soundcards = HardwareSerializer(
        many=True, read_only=True
    )
    equipment_acquisition_hardware_speakers = HardwareSerializer(
        many=True, read_only=True
    )
    equipment_acquisition_hardware_amplifiers = HardwareSerializer(
        many=True, read_only=True
    )
    equipment_acquisition_hardware_microphones = HardwareSerializer(
        many=True, read_only=True
    )
    references = ReferenceSerializer(many=True, read_only=True)
    created_by = CustomUserSerializer(read_only=True)

    # ---- Write fields POST/PUT/PATCH ----
    protocol_id = VisiblePrimaryKeyRelatedField(
        queryset=Protocol.objects.all(),
        source="protocol",
        write_only=True,
        required=False,
        allow_null=True,
    )
    study_ids = VisiblePrimaryKeyRelatedField(
        queryset=Study.objects.all(),
        source="studies",
        many=True,
        write_only=True,
        required=False,
    )
    laboratory_id = VisiblePrimaryKeyRelatedField(
        queryset=Laboratory.objects.all(),
        source="laboratory",
        write_only=True,
        required=False,
        allow_null=True,
    )
    animal_profile_ids = VisiblePrimaryKeyRelatedField(
        queryset=AnimalProfile.objects.all(),
        source="animal_profiles",
        many=True,
        write_only=True,
        required=False,
    )
    equipment_acquisition_software_ids = VisiblePrimaryKeyRelatedField(
        queryset=SoftwareVersion.objects.all(),
        source="equipment_acquisition_software",
        many=True,
        write_only=True,
        required=False,
    )
    equipment_acquisition_hardware_soundcard_ids = VisiblePrimaryKeyRelatedField(
        queryset=Hardware.objects.filter(type="soundcard"),
        source="equipment_acquisition_hardware_soundcards",
        many=True,
        write_only=True,
        required=False,
    )
    equipment_acquisition_hardware_speaker_ids = VisiblePrimaryKeyRelatedField(
        queryset=Hardware.objects.filter(type="speaker"),
        source="equipment_acquisition_hardware_speakers",
        many=True,
        write_only=True,
        required=False,
    )
    equipment_acquisition_hardware_amplifier_ids = VisiblePrimaryKeyRelatedField(
        queryset=Hardware.objects.filter(type="amplifier"),
        source="equipment_acquisition_hardware_amplifiers",
        many=True,
        write_only=True,
        required=False,
    )
    equipment_acquisition_hardware_microphone_ids = VisiblePrimaryKeyRelatedField(
        queryset=Hardware.objects.filter(type="microphone"),
        source="equipment_acquisition_hardware_microphones",
        many=True,
        write_only=True,
        required=False,
    )
    references_ids = VisiblePrimaryKeyRelatedField(
        queryset=Reference.objects.all(),
        source="references",
        many=True,
        write_only=True,
        required=False,
    )
    behavior_terms = OntologyTermsField("behavior")

    equipment_channels = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    equipment_sound_isolation = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )

    context_temperature_value = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    context_temperature_unit = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    context_brightness = serializers.FloatField(required=False, allow_null=True)

    is_multiple = serializers.BooleanField(required=False, default=False)

    # what an administrator still has to validate before the session can be shared
    pending_entries = serializers.SerializerMethodField()

    class Meta:
        model = RecordingSession
        fields = "__all__"

    def get_pending_entries(self, obj):
        request = self.context.get("request")
        view = self.context.get("view")
        user = getattr(request, "user", None)
        mine = (
            user
            and user.is_authenticated
            and (user.is_staff or obj.created_by_id == user.id)
        )
        detail = getattr(view, "action", None) in (
            "retrieve",
            "create",
            "update",
            "partial_update",
        )
        if not (mine and detail) or obj.status in ("shared", "published"):
            return []
        return [
            {"kind": kind, "id": entry.pk, "name": str(entry), "status": entry.status}
            for kind, entry in session_pending_entries(obj)
        ]

    # ---- Validation ----
    def validate(self, data):
        errors = {}
        user = self.context["request"].user

        # 1️⃣ validation on date if is_multiple is False
        is_multiple = data.get(
            "is_multiple", getattr(self.instance, "is_multiple", False)
        )

        if (
            not is_multiple
            and not data.get("date")
            and not getattr(self.instance, "date", None)
        ):
            errors["date"] = "A date is required for single recording sessions."

        # 2️⃣ Validation of non-None fields
        for field in ["name", "date"]:
            if field in data and data[field] is None:
                if field == "date" and is_multiple:
                    continue
                errors[field] = f"{field} cannot be None."

        # 3️⃣ Validation of uniqueness per user
        name = data.get("name", getattr(self.instance, "name", None))
        if name:
            qs = RecordingSession.objects.filter(name=name, created_by=user)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                errors["name"] = "You already have a recording session with this name."

        # 4️⃣ Raise ValidationError if necessary
        if errors:
            raise serializers.ValidationError(errors)

        return data

    # ---- Helpers ----
    def _extract_m2m(self, validated_data):
        return {
            "studies": validated_data.pop("studies", None),
            "animal_profiles": validated_data.pop("animal_profiles", None),
            "equipment_acquisition_software": validated_data.pop(
                "equipment_acquisition_software", None
            ),
            "equipment_acquisition_hardware_soundcards": validated_data.pop(
                "equipment_acquisition_hardware_soundcards", None
            ),
            "equipment_acquisition_hardware_microphones": validated_data.pop(
                "equipment_acquisition_hardware_microphones", None
            ),
            "equipment_acquisition_hardware_speakers": validated_data.pop(
                "equipment_acquisition_hardware_speakers", None
            ),
            "equipment_acquisition_hardware_amplifiers": validated_data.pop(
                "equipment_acquisition_hardware_amplifiers", None
            ),
            "references": validated_data.pop("references", None),
            "behavior_terms": validated_data.pop("behavior_terms", None),
        }

    def _assign_m2m(self, instance, m2m_fields):
        for field, value in m2m_fields.items():
            if value is not None:
                getattr(instance, field).set(value)

    # ---- Status ----
    def validate_status(self, value):
        user = self.context["request"].user
        if value == "published" and not user.is_staff:
            raise serializers.ValidationError(
                "A session becomes published through the deposit in a repository."
            )
        return value

    def _final_status(self, instance, requested, is_staff):
        """The status once the session is saved and its entries are known.

        An administrator sets what he wants. The owner asks for "shared" (or "waiting
        validation"): the session is shared at once when everything it uses is validated,
        otherwise it waits for a review of the new entries.
        """
        if requested is None:
            return instance.status
        if is_staff or requested == "draft":
            return requested
        return WAITING if session_pending_entries(instance) else "shared"

    # ---- Create ----
    def create(self, validated_data):
        request = self.context["request"]
        m2m_fields = self._extract_m2m(validated_data)
        laboratory = validated_data.pop("laboratory", None)
        requested = validated_data.pop("status", None)

        try:
            with transaction.atomic():
                instance = RecordingSession.objects.create(
                    **validated_data, laboratory=laboratory
                )
                self._assign_m2m(instance, m2m_fields)
                final = self._final_status(instance, requested, request.user.is_staff)
                if final != instance.status:
                    instance.status = final
                    instance.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(_django_errors(exc)) from None
        if instance.status == WAITING:
            notify_admin_review(instance)
        return instance

    # ---- Update ----
    def update(self, instance, validated_data):
        request = self.context["request"]
        is_staff = request.user.is_staff
        before = instance.status
        requested = validated_data.pop("status", None)

        # waiting for a review, shared or published: the owner can only withdraw his request
        withdraws = (
            before == WAITING
            and requested == "draft"
            and not validated_data
            and not self.initial_data.keys() - {"status"}
        )
        if not is_staff and before in SESSION_LOCKED and not withdraws:
            raise PermissionDenied(
                "This session is waiting for a review or already shared: "
                "it can no longer be edited."
            )

        m2m_fields = self._extract_m2m(validated_data)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if "laboratory" in validated_data:
            instance.laboratory = validated_data["laboratory"]

        try:
            with transaction.atomic():
                instance.save()  # checks the whole model: it may refuse
                self._assign_m2m(instance, m2m_fields)
                final = self._final_status(instance, requested, is_staff)
                if final != instance.status:
                    instance.status = final
                    instance.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(_django_errors(exc)) from None
        if instance.status == WAITING and before != WAITING:
            notify_admin_review(instance)
        return instance


class RecordingSessionShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecordingSession
        fields = ("id", "name")


class StudySerializer(ModerationMixin, serializers.ModelSerializer):
    recording_sessions = RecordingSessionShortSerializer(many=True, required=False)

    class Meta:
        model = Study
        fields = "__all__"
        read_only_fields = ("created_by",)  # set by the server, never by the client

    def validate(self, data):
        start = data.get("start_date", getattr(self.instance, "start_date", None))
        end = data.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "The end date cannot be before the start date."}
            )
        return data


class FileSerializer(serializers.ModelSerializer):
    repository_id = serializers.PrimaryKeyRelatedField(
        source="repository",
        queryset=Repository.objects.all(),
        required=False,
        write_only=True,
    )
    repository = RepositorySerializer(required=False)
    recording_session_id = serializers.PrimaryKeyRelatedField(
        source="recording_session",
        queryset=RecordingSession.objects.all(),
        required=False,
        write_only=True,
    )
    recording_session = RecordingSessionSerializer(required=False)
    subjects = SubjectSerializer(many=True, required=False)
    created_by = CustomUserSerializer(read_only=True)

    class Meta:
        model = File
        fields = "__all__"

    def validate(self, attrs):
        # Validate DOI format
        if "doi" in attrs:
            attrs["doi"] = validate_doi(attrs["doi"])

        # Valider URL format
        if "link" in attrs:
            attrs["link"] = validate_url(attrs["link"])

        # Validate consistency between DOI and link
        return validate_doi_link_consistency(attrs)


class FileNestedSerializer(serializers.ModelSerializer):
    plot_url = serializers.SerializerMethodField()
    spectrogram_url = serializers.SerializerMethodField()
    session = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = [
            "id",
            "name",
            "link",
            "doi",
            "plot_url",
            "spectrogram_url",
            "status",
            "downloads",
            "session",
        ]

    def get_session(self, obj):
        """Short description of the session, shown as chips next to the file."""
        rs = obj.recording_session
        if rs is None:
            return None
        p = rs.protocol
        chips = (
            [
                value
                for value in (
                    p.animals_sex,
                    p.animals_age,
                    p.context_duration,
                    p.context_cage,
                    p.context_bedding,
                )
                if value and value != "unspecified"
            ]
            if p
            else []
        )
        return {
            "name": rs.name,
            "chips": chips,
            "animal_profiles": [a.name for a in rs.animal_profiles.all()],
        }

    def get_plot_url(self, obj):
        if obj.plot and hasattr(obj.plot, "url"):
            request = self.context.get("request")
            return request.build_absolute_uri(obj.plot.url) if request else obj.plot.url
        return None

    def get_spectrogram_url(self, obj):
        if obj.spectrogram and hasattr(obj.spectrogram, "url"):
            request = self.context.get("request")
            return (
                request.build_absolute_uri(obj.spectrogram.url)
                if request
                else obj.spectrogram.url
            )
        return None


class DatasetSerializer(serializers.ModelSerializer):
    files = serializers.SerializerMethodField()
    # read: id and name of the sessions; write (admins only): ids
    recording_sessions = serializers.SerializerMethodField()
    recording_session_ids = serializers.PrimaryKeyRelatedField(
        queryset=RecordingSession.objects.all(),
        source="recording_session_list",
        many=True,
        write_only=True,
        required=False,
    )

    class Meta:
        model = Dataset
        fields = [
            "id",
            "name",
            "description",
            "link",
            "doi",
            "files",
            "recording_sessions",
            "recording_session_ids",
        ]

    def get_recording_sessions(self, obj):
        return [
            {"id": rs.id, "name": rs.name}
            for rs in obj.recording_session_list.order_by("name")
        ]

    def get_files(self, obj):
        files_qs = (
            File.objects.filter(recording_session__in=obj.recording_session_list.all())
            .select_related("recording_session__protocol")
            .prefetch_related("recording_session__animal_profiles")
        )
        serializer = FileNestedSerializer(files_qs, many=True, context=self.context)
        return serializer.data


MODEL_MAP = {
    "protocol": Protocol,
    "software": Software,
    "hardware": Hardware,
    "animalprofile": AnimalProfile,
    "strain": Strain,
    "species": Species,
    "reference": Reference,
    "contact": Contact,
}


class FavoriteSerializer(serializers.ModelSerializer):
    content_type = serializers.SerializerMethodField()
    content_type_name = serializers.CharField(write_only=True)

    class Meta:
        model = Favorite
        fields = "__all__"
        read_only_fields = ("user", "created_at")

    def get_content_type(self, obj):
        return obj.content_type.model.lower()

    def validate(self, data):
        user = self.context["request"].user
        model_name = (data.get("content_type_name") or "").lower()

        if model_name not in Favorite.ALLOWED_MODELS:
            raise serializers.ValidationError(
                f"Favorites of type '{model_name}' are not allowed."
            )

        try:
            content_type = ContentType.objects.get(
                app_label="mousetube_api", model=MODEL_MAP[model_name]._meta.model_name
            )
        except ContentType.DoesNotExist:
            raise serializers.ValidationError(
                f"ContentType '{model_name}' does not exist."
            )

        object_id = data.get("object_id")
        if object_id is None:
            raise serializers.ValidationError("object_id is required.")

        ModelClass = MODEL_MAP[model_name]
        try:
            obj = ModelClass.objects.get(pk=object_id)
        except ModelClass.DoesNotExist:
            raise serializers.ValidationError(
                f"{model_name.capitalize()} with id {object_id} does not exist."
            )

        is_owner = getattr(obj, "created_by", None) == user
        is_validated = getattr(obj, "status", None) == "validated"
        if not (is_owner or is_validated):
            raise serializers.ValidationError(
                f"You can only favorite your own {model_name}s or validated ones."
            )
        data["content_type"] = content_type

        return data

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        validated_data.pop("content_type_name", None)
        return super().create(validated_data)


class PageViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageView
        fields = "__all__"


class TrackPageSerializer(serializers.Serializer):
    path = serializers.CharField(max_length=255)

    def validate_path(self, value):
        # keep the page, drop query/fragment: otherwise every ?x=<random> is a new row
        value = value.split("?")[0].split("#")[0]
        if not value.startswith("/") or any(c.isspace() or ord(c) < 32 for c in value):
            raise serializers.ValidationError("Invalid path.")
        return value
