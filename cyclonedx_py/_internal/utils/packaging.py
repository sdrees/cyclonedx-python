# This file is part of CycloneDX Python Lib
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) OWASP Foundation. All Rights Reserved.

from re import compile as re_compile
from typing import TYPE_CHECKING, Generator, List

from cyclonedx.exception.model import InvalidUriException
from cyclonedx.factory.license import LicenseFactory
from cyclonedx.model import AttachedText, ExternalReference, ExternalReferenceType, XsUri
from cyclonedx.model.license import DisjunctiveLicense, LicenseAcknowledgement

from .cdx import url_label_to_ert
from .pep621 import classifiers2licenses

if TYPE_CHECKING:  # pragma: no cover
    import sys

    from cyclonedx.model.license import License

    if sys.version_info >= (3, 10):
        from importlib.metadata import PackageMetadata
    else:
        from email.message import Message as PackageMetadata


def metadata2licenses(metadata: 'PackageMetadata') -> Generator['License', None, None]:
    lfac = LicenseFactory()
    lack = LicenseAcknowledgement.DECLARED
    if 'Classifier' in metadata:
        # see spec: https://packaging.python.org/en/latest/specifications/core-metadata/#classifier-multiple-use
        classifiers: List[str] = metadata.get_all('Classifier')  # type:ignore[assignment]
        yield from classifiers2licenses(classifiers, lfac, lack)
    for mlicense in metadata.get_all('License', ()):
        # see spec:  https://packaging.python.org/en/latest/specifications/core-metadata/#license
        if len(mlicense) <= 0:
            continue
        license = lfac.make_from_string(mlicense,
                                        license_acknowledgement=lack)
        if isinstance(license, DisjunctiveLicense) and license.id is None:
            # per spec, `License` is either a SPDX ID/Expression, or a license text(not name!)
            yield DisjunctiveLicense(name=f"declared license of '{metadata['Name']}'",
                                     acknowledgement=lack,
                                     text=AttachedText(content=mlicense))
        else:
            yield license
    # TODO: iterate over "License-File" declarations and read them
    # for mlfile in  metadata.get_all('License-File'): ...


def metadata2extrefs(metadata: 'PackageMetadata') -> Generator['ExternalReference', None, None]:
    for meta_key, extref_typet in (
        # see https://packaging.python.org/en/latest/specifications/core-metadata/#home-page
        ('Home-page', ExternalReferenceType.WEBSITE),
        # see https://packaging.python.org/en/latest/specifications/core-metadata/#download-url
        ('Download-URL', ExternalReferenceType.DISTRIBUTION),
    ):
        if meta_key in metadata:
            try:
                yield ExternalReference(
                    comment=f'from packaging metadata: {meta_key}',
                    type=extref_typet,
                    url=XsUri(metadata[meta_key]))
            except InvalidUriException:  # pragma: nocover
                pass
    for label_url in metadata.get_all('Project-URL', ()):
        # see https://packaging.python.org/en/latest/specifications/core-metadata/#project-url-multiple-use
        label, url = label_url.split(',', maxsplit=1)
        try:
            yield ExternalReference(
                comment=f'from packaging metadata Project-URL: {label}',
                type=url_label_to_ert(label),
                url=XsUri(url.strip()))
        except InvalidUriException:  # pragma: nocover
            pass


_NORMALIZE_PN_MATCHER = re_compile(r'[-_.]+')
_NORMALIZE_PN_REPLACE = '-'


def normalize_packagename(name: str) -> str:
    """
    Normalize package names.
    Also applies to names of package extras.

    see https://packaging.python.org/en/latest/specifications/name-normalization/#name-normalization
    """
    return _NORMALIZE_PN_MATCHER.sub(_NORMALIZE_PN_REPLACE, name).lower()
