# Repo Map: Helpybo Module Custom Flow

- Fingerprint: c0c9fa553cc2732823b695d045b56d712c094a18
- Indexed files: 932

## Top Directories
- `helpybotest`: 1119 files

## Important Files
- `helpybotest/helpybotest/urls.py`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 17 lines. Key imports: from django.contrib import admin, from django.urls import include, path, from django.conf import settings, from django.conf.urls.static import static, from django.views.generic import RedirectView.
- `helpybotest/accounts/urls.py`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 62 lines. Key imports: from django.urls import path, from . import views.
- `helpybotest/manage.py`: Configuration file that controls tooling, runtime behavior, or project conventions. It has about 22 lines. Primary symbol: main. Top headings: !/usr/bin/env python. Key imports: import os, import sys, from django.core.management import execute_from_command_line.
- `helpybotest/static/js/main.js`: Source file that contributes to the `helpybotest/static/js` area of the repository. It has about 14 lines.
- `helpybotest/helpybotest/settings.py`: Source file that contributes to the `helpybotest/helpybotest` area of the repository. It has about 165 lines. Top headings: Build paths inside the project like this: BASE_DIR / 'subdir'., Quick-start development settings - unsuitable for production, See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/, SECURITY WARNING: keep the secret key used in production secret!, SECURITY WARNING: don't run with debug turned on in production!. Key imports: from pathlib import Path, import os.
- `helpybotest/helpybotest/asgi.py`: Source file that contributes to the `helpybotest/helpybotest` area of the repository. It has about 16 lines. Key imports: import os, from django.core.asgi import get_asgi_application.
- `helpybotest/helpybotest/wsgi.py`: Source file that contributes to the `helpybotest/helpybotest` area of the repository. It has about 16 lines. Key imports: import os, from django.core.wsgi import get_wsgi_application.
- `helpybotest/accounts/models.py`: Data model or type-definition file describing the shapes the application stores, exchanges, or validates. It has about 172 lines. Primary symbol: User. Top headings: In models.py, add to ChatHistory. Key imports: from django.db import models, from django.contrib.auth.models import AbstractUser, from django.db.models import JSONField, from django.db import models.
- `helpybotest/accounts/views.py`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 2503 lines. Primary symbol: generate_session_id. Top headings: Force HTTPS for media URLs only, Keep original chat response URL construction, def generate_chat_widget(request, user):, try:, chatbot = Chatbot.objects.get(user=user). Key imports: import os, import json, import re, import uuid, import time. Representative commands: shutil.copy2(file_path, new_file_path), shutil.rmtree(user_pdf_folder), shutil.rmtree(user_vector_db_path).
- `helpybotest/views.py`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 24 lines. Primary symbol: api_create_flow. Top headings: ...existing code..., Add @csrf_exempt to other API views as needed. Key imports: from django.views.decorators.csrf import csrf_exempt.
- `helpybotest/view1.py`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 1334 lines. Primary symbol: generate_session_id. Top headings: chat_response_url = request.build_absolute_uri(reverse('chat_response', args=[user.id])).replace("http://", "https://"), Calculate date range for filtering, Get all chat histories for this user's chatbot, Calculate basic statistics, Get unique session IDs. Key imports: import os, import json, import re, import uuid, import time. Representative commands: shutil.copy2(file_path, new_file_path), shutil.rmtree(user_pdf_folder), shutil.rmtree
- `helpybotest/media/sample_pages/user_11_sample.html`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 54 lines. Primary symbol: adjustWidgetForMobile.
- `helpybotest/media/sample_pages/user_12_sample.html`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 54 lines. Primary symbol: adjustWidgetForMobile.
- `helpybotest/media/sample_pages/user_13_sample.html`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 54 lines. Primary symbol: adjustWidgetForMobile.
- `helpybotest/media/sample_pages/user_2_sample.html`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 54 lines. Primary symbol: adjustWidgetForMobile.
- `helpybotest/media/sample_pages/user_4_sample.html`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 54 lines. Primary symbol: adjustWidgetForMobile.
- `helpybotest/media/sample_pages/user_5_sample.html`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 54 lines. Primary symbol: adjustWidgetForMobile.
- `helpybotest/media/sample_pages/user_6_sample.html`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 54 lines. Primary symbol: adjustWidgetForMobile.
- `helpybotest/media/sample_pages/user_7_sample.html`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 54 lines. Primary symbol: adjustWidgetForMobile.
- `helpybotest/media/sample_pages/user_8_sample.html`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 54 lines. Primary symbol: adjustWidgetForMobile.
- `helpybotest/media/sample_pages/user_9_sample.html`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 54 lines. Primary symbol: adjustWidgetForMobile.
- `helpybotest/templates/sample_widget_page.html`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 54 lines. Primary symbol: adjustWidgetForMobile.
- `helpybotest/templates/preview_chatbot.html`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 27 lines. Top headings: chat-widget{, chat-button{, chat-button:hover{.
- `helpybotest/templates/view_products.html`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 193 lines.

## Project Instructions
- `.devhub/DEVHUB.md`

## Repo Tree
```text
Helpybo Module Custom Flow/
|- .devhub/
|- helpybotest/
`- helpybotest
   |- accounts
   |  |- migrations
   |  |  `- __init__.py
   |  |- __init__.py
   |  |- admin.py
   |  |- apps.py
   |  |- chatbot_logic.py
   |  |- forms.py
   |  |- models.py
   |  |- templatetags.py
   |  |- tests.py
   |  |- urls.py
   |  `- views.py
   |- chat_histories
   |  |- user_11_00d0782e-059e-44cf-b5d1-18910268d7ed.json
   |  |- user_11_01fc6804-4e84-4c14-b08a-0858daebaf61.json
   |  |- user_11_024a758f-4097-4818-8c5b-b99dc31c55ad.json
   |  |- user_11_027b5729-0d2b-42b6-a710-598918d1483f.json
   |  |- user_11_048df43f-bba9-490b-8daf-df4c97eb45f6.json
   |  |- user_11_08ba8218-c8c3-4071-863a-2e5a40a09bca.json
   |  |- user_11_09ff25af-0d54-49e4-8794-f7ac3eba4c63.json
   |  |- user_11_0be8a1d8-8380-4668-ac07-8020fdc2d179.json
   |  |- user_11_115535db-6228-4522-96dd-f880896343c2.json
   |  |- user_11_1639bbdf-79a7-4bbb-b610-2c43c742a5ef.json
   |  |- user_11_16e8157d-2cbf-4a72-a91b-94dfaa5571df.json
   |  |- user_11_1707b409-2947-4a8e-a47c-80d8ce80fa8a.json
   |  |- user_11_190ab359-c1cb-4fee-94f4-4d2b0f198312.json
   |  |- user_11_1b6d672c-89ab-44e7-874c-36cc8d2158b5.json
   |  |- user_11_1d1868ac-c769-444b-bcff-7225e0d89e61.json
   |  |- user_11_1f054c72-e6d1-4be8-b508-d7c0fcc99758.json
   |  |- user_11_1f1e0d44-386e-4c39-bb0d-732c38d321c1.json
   |  |- user_11_1f5c0d77-caf2-4f8f-87e3-540a0b56dcce.json
   |  |- user_11_21878249-5b1f-4761-9232-ccb8889f68bb.json
   |  |- user_11_24e26adf-9de4-4e49-bbe4-e22c2c046478.json
   |  |- user_11_28715746-f7c8-4715-be41-0a3208c10568.json
   |  |- user_11_298e5f65-2093-4256-91ea-7c6b4962cc68.json
   |  |- user_11_2a20d2e7-dd13-4c42-89e1-7d1280a9b94b.json
   |  |- user_11_2c3b2fd6-24d1-4c71-a2da-e4220cc4d094.json
   |  |- user_11_2da5afbf-0848-4245-9911-1c6d49bc70c3.json
   |  |- user_11_2fc0e2dd-301b-45ac-a4ee-eaa90633260b.json
   |  |- user_11_314ec380-e4f7-4908-80d8-57ea45dc2148.json
   |  |- user_11_32b038eb-22ef-47e2-8f14-6371583abedc.json
   |  |- user_11_333434a2-5681-4317-9126-be8ce73095b4.json
   |  |- user_11_38e507f9-6283-40c9-a8d9-20e5e6220f56.json
   |  |- user_11_39f50e16-72a2-4997-bc7a-486ee7e62a87.json
   |  |- user_11_3a28fef5-4aea-4195-be63-e8d12bed7669.json
   |  |- user_11_3aa5a4df-a99e-49e8-bdef-ad1a38e75ec9.json
   |  |- user_11_3b87c149-90ff-4df1-9023-9056e73afa98.json
   |  |- user_11_3cb84907-a0b9-4a30-92cd-0bb20f40efe0.json
   |  |- user_11_3cb92573-2156-4583-8e96-f525a830c1eb.json
   |  |- user_11_3cdb7ddd-0d01-4150-8150-b9efb4a242d9.json
   |  |- user_11_421a95eb-aee2-4f0f-bdb1-830259cfb605.json
   |  |- user_11_42fe06c5-3946-49e0-9f6c-45b8008d1ac6.json
   |  |- user_11_4696daf6-6cf4-496a-8703-22cde9a38fc9.json
   |  |- user_11_47df7f14-f0c3-465e-8844-4ae2f45d753f.json
   |  |- user_11_49c5c437-f069-417a-b9d7-5cc795337d8d.json
   |  |- user_11_4cd5c7c3-7b3f-4078-81bc-2eef47e17aea.json
   |  |- user_11_4f586d06-dde0-4858-8474-dc0c4e99765e.json
   |  |- user_11_4fa2aa36-9114-4407-8402-0ddcd874b216.json
   |  |- user_11_51c7b8aa-20e2-4c91-a14d-de9aa63d7239.json
   |  |- user_11_527c680e-df1a-4be9-9e2c-7115a40d41b5.json
   |  |- user_11_5290d1fa-d596-478d-b40e-e0f0abf6ba04.json
   |  |- user_11_536a5cb2-81e4-4001-a4a6-d046b31b6576.json
   |  |- user_11_55264f5c-c696-4f19-9951-00eabf91446f.json
   |  |- user_11_588982c7-afcb-441b-87a2-2358c9c56c18.json
   |  |- user_11_59524721-e0d9-45db-a18f-fdad880528b0.json
   |  |- user_11_59cacc8c-e133-435b-b0dc-60c9bac8468e.json
   |  |- user_11_5c907c73-82a7-4be7-a11e-f467ee553b7f.json
   |  |- user_11_5d5aa2f4-dd34-4c79-bf1d-0a15a2de60bc.json
   |  |- user_11_5dfe3a2e-c54c-4374-b6f4-b54bebbe9f68.json
   |  |- user_11_601e2ee5-46e5-4f50-85c8-0a9f69a0f497.json
   |  |- user_11_6094aa29-970b-4b98-b8c7-55795f193f96.json
   |  |- user_11_6568c386-4697-4b70-b590-51e21e49acb0.json
   |  |- user_11_673b0358-742d-47ee-88fb-4b52ca82b371.json
   |  |- user_11_68f8e234-e424-4204-891c-865e8042d7be.json
   |  |- user_11_6982775a-3530-4ca6-b9f4-35181ce8ca30.json
   |  |- user_11_69f9469c-020c-4932-80d5-2bf9600116c6.json
   |  |- user_11_6ac476fd-bda7-419d-ae52-17bd02367a70.json
   |  |- user_11_6b66f4c8-4195-4e51-9e2a-b058edab76ff.json
   |  |- user_11_6cb23bfa-a0f9-42a6-8887-6d26901c3e19.json
   |  |- user_11_6cb2422e-200e-4cb4-91f3-cdbffe91299c.json
   |  |- user_11_70dfe7a4-e650-4688-80ee-2fb8bd4dab06.json
   |  |- user_11_742a7a43-e1cc-428b-bf5c-6fc069a49ba5.json
   |  |- user_11_7518d96a-02e8-4d2c-b397-75e55b94a739.json
   |  |- user_11_76b13f1b-8da0-44c6-af4d-26bfd703f480.json
   |  |- user_11_78d05ae2-30ec-4f9f-91b0-4ab2ed542354.json
   |  |- user_11_78eafc31-48df-477e-8269-1b01a4a62763.json
   |  |- user_11_7a8f16f6-96be-45ee-80dd-6989c8b2f5ff.json
   |  |- user_11_819a93c7-1610-4af9-866d-a8f0e595fa53.json
   |  |- user_11_85d86280-29b1-465c-817f-d1370ed67387.json
   |  |- user_11_87ef5a2c-c994-4e62-a930-779b6e2ac449.json
   |  |- user_11_8cb46346-1b16-43b5-b607-aa5e1a9ab3c2.json
   |  |- user_11_8d1e1973-5898-476e-ad3f-2caa508878ba.json
   |  |- user_11_8f56c9dd-b35b-4095-892a-a8ce3d485c2c.json
   |  |- user_11_8fa3dd18-c71a-44b3-aac3-ec9838f61532.json
   |  |- user_11_8ff71140-d979-4691-984a-c2bc72c9adaf.json
   |  |- user_11_90e49e02-537e-4bc3-aac4-ae08a3382061.json
   |  |- user_11_92613f75-7925-4b52-bed3-64184b0fcc61.json
   |  |- user_11_954ef1ac-a2ec-4e9e-9f0e-23c023716d8f.json
   |  |- user_11_95e134ac-f353-4838-82ef-931816a3c598.json
   |  |- user_11_988a2480-8557-4ff3-8c83-2177d5cd5951.json
   |  |- user_11_9c62f720-cfa7-4f7e-b9df-ccdcaf5125f6.json
   |  |- user_11_9e45a39f-e337-42ce-ae61-5dd7c8bf5c5e.json
   |  |- user_11_9f767fc8-584e-41e1-b9b0-d7efe2f8a7a6.json
   |  |- user_11_9f8f6e64-58df-4fcb-9b4b-9b0255f6f80c.json
   |  |- user_11_a224a846-b7d7-41aa-8c0c-3665aeb0706d.json
   |  |- user_11_a27a3aaa-79a0-4a51-9efa-1d1bc05676fe.json
   |  |- user_11_a35b85ea-4c86-4a2c-93d8-57ef41b0c155.json
   |  |- user_11_a3a118db-dc82-42d0-a34b-9deeec6adc2d.json
   |  |- user_11_a469b742-466c-46ee-a50e-34580e978cd6.json
   |  |- user_11_a4a3b007-6a72-4945-9947-2658b423ccc4.json
   |  |- user_11_a509226c-03a1-4873-b583-05bd60b4e473.json
   |  |- user_11_af6308ab-0f99-4612-b2c3-43d23ca050b5.json
   |  |- user_11_afdc9c6d-564e-41a2-b30b-511fa32fe301.json
   |  |- user_11_b4db42f3-8a79-4a3d-8617-70a88970628c.json
   |  |- user_11_b506ec51-23ce-4d42-98e2-67f63b214cae.json
   |  |- user_11_b9c20cfb-b465-4512-a67a-4fff2f4b757c.json
   |  |- user_11_ba5473ad-b28b-4a6e-a482-3b4c640ad5f0.json
   |  |- user_11_be12badb-37d6-4c19-8646-cb2817b5f63f.json
   |  |- user_11_be3e4b8c-c5b9-4993-ad2c-6a11695d774b.json
   |  |- user_11_bf390400-4180-40d8-a223-df1767009c45.json
   |  |- user_11_c46fc759-458c-4e6c-bdce-87d4b998f69e.json
   |  |- user_11_cad27869-2f03-442f-8deb-f5282a156410.json
   |  |- user_11_cf9fa80b-365b-4a7e-ba93-bf91acb2b39c.json
   |  |- user_11_d2853ab4-d548-41d0-af28-04b36d72a40e.json
   |  |- user_11_d2f4d881-1fdc-49ae-9d9f-c4d6c526265c.json
   |  |- user_11_d5ba9316-d15e-45c8-9e06-4f42fbe69ba0.json
   |  |- user_11_d720415d-5404-49d6-8799-3ffa4af323b0.json
   |  |- user_11_d9656f27-0583-47ff-bc85-b97c49b64fa3.json
   |  |- user_11_da325bf4-a864-4f05-9d3a-a40814def891.json
   |  |- user_11_dc915f5b-8ec0-44d3-a67b-bb8a764f97bf.json
   |  |- user_11_de2493e3-0c6d-46ff-b32f-14455af6e41b.json
   |  |- user_11_df560173-a490-4d49-b0d8-243c367e3f72.json
   |  |- user_11_e17b06a6-1cca-4166-92ef-5d6a02671377.json
   |  |- user_11_e30e13ff-d23f-4afa-b76f-61bbe7d1b07a.json
   |  |- user_11_e3535043-93b0-49a4-9949-a92ac197823e.json
   |  |- user_11_e3647e70-4979-41fb-be10-5f74e5476914.json
   |  |- user_11_e730086b-c994-4afe-8844-5d9598e0f72d.json
   |  |- user_11_e8baaf3a-d24f-4862-99c4-e10e4e457221.json
   |  |- user_11_e9f9ea89-3c30-47a6-8dfe-8b91c317a5ff.json
   |  |- user_11_eb020ee7-7b6e-431f-81a7-29ab45cd3eae.json
   |  |- user_11_ed375fff-55f5-45df-9bdb-a80160babc58.json
   |  |- user_11_ee199647-a37b-4650-874f-ca6af1b9f156.json
   |  |- user_11_ef706bf8-d060-42c3-99a1-3dbcfcfb83f6.json
   |  |- user_11_eff26905-a312-4324-982c-8e3072bc9eaf.json
   |  |- user_11_f4fbf7fe-4aa2-4da0-a050-e02ae421f2a4.json
   |  |- user_11_f50a02f0-7b19-46f5-95a3-7f6d62ee6679.json
   |  |- user_11_f6428cc5-e4c0-4077-8fda-6e685ca16832.json
   |  |- user_11_f81ec1ed-359b-4901-bf37-5765372e3b73.json
   |  |- user_11_f971abb0-f733-43f1-ac4e-85991c8e3f94.json
   |  |- user_11_f9f4bf19-519d-42fc-981a-aebbfa3e7c2d.json
   |  |- user_11_fa25c84c-d800-4d24-b325-eea41ec6ca35.json
   |  |- user_11_fc34d1ba-0be1-4964-853d-e9675d5fd05c.json
   |  |- user_11_fc3c403d-686a-4a7a-b348-ce7f38939f7d.json
   |  |- user_11_fdf1e4b1-9dc9-4465-a1b6-8630a0d156e2.json
   |  |- user_12_0d2d6c96-8f72-41d6-b732-2e6e8b93ed52.json
   |  |- user_12_12071d1c-dc95-4c05-ad6d-79bfbb995177.json
   |  |- user_12_18590d20-8c49-491f-a59a-14974c4f79d0.json
   |  |- user_12_24f77a5d-f584-4da3-8df8-c1c25f2f99ca.json
   |  |- user_12_2c59cb93-e145-4257-a5d1-ae48df504da6.json
   |  |- user_12_3212bc0d-4334-451b-9965-26f78a163c76.json
   |  |- user_12_3457f507-3516-44e3-9194-a965943de761.json
   |  |- user_12_3fdd1366-4d43-4a72-afae-ce51eee14bc3.json
   |  |- user_12_45ae25e0-76cf-499a-b7e1-921f2e25fa4f.json
   |  |- user_12_55b29949-cd18-45c2-be14-db615845e6b0.json
   |  |- user_12_56182af4-3ab9-411f-81f5-13b840c2346f.json
   |  |- user_12_583e59a4-4451-4b5a-bdd1-faed962f3136.json
   |  |- user_12_5d404109-ebbe-4c30-90ea-000d4fb31fee.json
   |  |- user_12_5f030104-db4f-4c75-8769-b91ded36b46e.json
   |  |- user_12_705677ff-a961-4d9e-aa99-ddfee1d6961c.json
   |  |- user_12_728d2244-18d3-4647-950c-e365053a82d8.json
   |  |- user_12_799ece74-49d1-4a24-9ccd-5559410cd0fe.json
   |  |- user_12_816ff5cb-0906-434d-91fd-1f2c37d4fe0e.json
   |  |- user_12_85a415f2-7375-4671-901f-c288be40e34b.json
   |  |- user_12_8bb45cdb-9efd-41e2-8309-a9fe2ea58397.json
   |  |- user_12_a741b5de-c910-4889-8447-1f3d82a1f12d.json
   |  |- user_12_ab06ba4e-b33d-4cf4-8828-44fcbe18e65e.json
   |  |- user_12_ad644464-fb30-4b52-b21f-c56c16af1c9b.json
   |  |- user_12_b9d9e06e-4813-4cf6-a402-7d33f400ee52.json
   |  |- user_12_bd14938f-fdd7-451a-8bb2-86394cf60c07.json
   |  |- user_12_c3c02027-a7ce-4e68-a165-a13214f2aab0.json
   |  |- user_12_c578df09-bd76-4a75-9c6f-d277a12c6eac.json
   |  |- user_12_d3cc7a80-1c22-4585-989d-af079261643f.json
   |  |- user_12_d70b0d37-6fcc-472d-b30e-b700b5a24242.json
   |  |- user_12_dc4e3cfc-4d90-4226-bcfa-2dafd9b1f5f2.json
   |  |- user_12_e1d3a640-7720-4301-b3a4-8dd38690fadf.json
   |  |- user_12_e263af19-af2c-4d2e-83c4-bd1a87863fc5.json
   |  |- user_12_e4306ea2-dc06-4974-ae05-2f4eec41c6e7.json
   |  |- user_12_e94cdf19-5044-44ca-874f-868d38390fc8.json
   |  |- user_12_ea6c90b7-841d-46d9-8db6-7867412c725f.json
   |  |- user_12_f0c4db83-1b43-41ce-8f87-867b982a598b.json
   |  |- user_12_f72e58c0-1162-492a-abab-fc1f8744f44f.json
   |  |- user_13_0cc8ba80-c426-419e-81aa-efc6fd992d96.json
   |  |- user_13_402e01f6-8c63-4e2d-b821-c66421fd820f.json
   |  |- user_13_6919c2d0-06be-41de-8ec1-4266e298cd0e.json
   |  |- user_13_a8080f5f-ed01-4b42-bbaf-8a5d125c5e0d.json
   |  |- user_13_ee4d5b7d-1584-4a57-a9e6-0ec77ef8c8f6.json
   |  |- user_2_02ceb628-1479-4054-941a-f7da31fcb6d7.json
   |  |- user_2_03f711c8-350c-4c6f-b687-43f5b1d84326.json
   |  |- user_2_042583e5-3ac6-4ed3-857a-36b86971da3e.json
   |  |- user_2_04b14a6c-896a-4205-aaec-e890fce7ca72.json
   |  |- user_2_04c712d5-b941-4513-8559-e67e983c21b5.json
   |  |- user_2_057e7c6e-4a99-4f62-9627-559acc7164de.json
   |  |- user_2_0581c16c-e28a-40a0-97f6-5ae0ee2cbc65.json
   |  |- user_2_059f9839-4044-4c7e-ab6e-82ab60b5d41a.json
   |  |- user_2_0604e414-0894-45e3-8af9-bb4bbf31abb0.json
   |  |- user_2_066f179e-0998-4a0e-9263-d4f8327a47fe.json
   |  |- user_2_074b4a1e-70b5-4df4-b3f6-c3cee83c05c0.json
   |  |- user_2_077a2f09-cc28-4fd9-a527-0a35d5926b9f.json
   |  |- user_2_08b5ed71-4cc7-451f-bc94-e4088781a1f3.json
   |  |- user_2_09e98925-806d-4cd5-a570-898003f1379c.json
   |  |- user_2_0a9bb106-04e0-463d-82ff-0e6
```