#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

SE050_AUTHID_USER_ID = 0x7DA00001

SE050_AUTHID_USER_ID_VALUE = [0xC0, 0x01, 0x02, 0x03, 0x04]

SE050_AUTHID_ECKEY = 0x7DA00003

SSS_AUTH_SE05X_KEY_HOST_ECDSA_KEY = [
    0x30, 0x81, 0x87, 0x02, 0x01, 0x00, 0x30, 0x13,
    0x06, 0x07, 0x2A, 0x86, 0x48, 0xCE, 0x3D, 0x02,
    0x01, 0x06, 0x08, 0x2A, 0x86, 0x48, 0xCE, 0x3D,
    0x03, 0x01, 0x07, 0x04, 0x6D, 0x30, 0x6B, 0x02,
    0x01, 0x01, 0x04, 0x20,
    0x6D, 0x2F, 0x43, 0x2F, 0x8A, 0x2F, 0x45, 0xEC,
    0xD5, 0x82, 0x84, 0x7E, 0xC0, 0x83, 0xBB, 0xEB,
    0xC2, 0x3F, 0x1D, 0xF4, 0xF0, 0xDD, 0x2A, 0x6F,
    0xB8, 0x1A, 0x24, 0xE7, 0xB6, 0xD5, 0x4C, 0x7F,
    0xA1, 0x44, 0x03, 0x42, 0x00,
    0x04, 0x3C, 0x9E, 0x47, 0xED, 0xF0, 0x51, 0xA3,
    0x58, 0x9F, 0x67, 0x30, 0x2D, 0x22, 0x56, 0x7C,
    0x2E, 0x17, 0x22, 0x9E, 0x88, 0x83, 0x33, 0x8E,
    0xC3, 0xB7, 0xD5, 0x27, 0xF9, 0xEE, 0x71, 0xD0,
    0xA8, 0x1A, 0xAE, 0x7F, 0xE2, 0x1C, 0xAA, 0x66,
    0x77, 0x78, 0x3A, 0xA8, 0x8D, 0xA6, 0xD6, 0xA8,
    0xAD, 0x5E, 0xC5, 0x3B, 0x10, 0xBC, 0x0B, 0x11,
    0x09, 0x44, 0x82, 0xF0, 0x4D, 0x24, 0xB5, 0xBE,
    0xC4,
]

SE050_AUTHID_AESKEY = 0x7DA00002
SE050_AUTHID_AESKEY_VALUE = [0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47,
                             0x48, 0x49, 0x4a, 0x4b, 0x4c, 0x4d, 0x4e, 0x4f, ]

SE050_AUTHID_PLATFORM_SCP = 0x7FFF0207
SE050_AUTHID_PLATFORM_SCP_VALUE = [0x70, 0x9e, 0x6c, 0xdb, 0xb7, 0x97, 0x6c, 0x48,
                                   0xa1, 0x6a, 0x9a, 0x59, 0x38, 0xc2, 0x7c, 0x7b,
                                   0xc6, 0x7c, 0x7e, 0x98, 0x61, 0x1e, 0x7c, 0x9e,
                                   0xe7, 0xcb, 0x8a, 0x4b, 0x79, 0x03, 0x9a, 0x91, ]

# This key version is constant for platform scp
SE05X_KEY_VERSION_NO = 0x0B