# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Helper utilities for managing test data."""

import logging
from pathlib import Path

import boto3


def _get_sample_csv_path() -> Path:
    """Get path to the static sample csv file.

    Returns:
        Path: Absolute path to LOAD001.csv in test/e2e/resources/data/
    """
    current_dir = Path(__file__).parent
    csv_path = current_dir / "resources" / "data" / "LOAD001.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Sample csv file not found at {csv_path}. "
            "Please ensure test/e2e/resources/data/LOAD001.csv exists."
        )
    return csv_path


def _load_sample_csv_bytes() -> bytes:
    """Load the static sample csv file as bytes.

    Returns:
        bytes: csv file content
    """
    csv_path = _get_sample_csv_path()
    with open(csv_path, 'rb') as f:
        return f.read()


def upload_csv_to_s3(
    bucket_name: str,
    s3_key: str = 'source/public/customers/LOAD001.csv'
) -> str:
    """Upload static sample csv data to S3 source folder.

    Args:
        bucket_name: Name of the S3 bucket
        s3_key: S3 object key (default: source/public/customers/LOAD001.csv)

    Returns:
        str: S3 URI of uploaded file (s3://bucket/key)

    Raises:
        FileNotFoundError: If sample csv file is not found
        Exception: If S3 upload fails
    """
    s3 = boto3.client('s3')
    csv_bytes = _load_sample_csv_bytes()

    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=csv_bytes,
            ContentType='application/octet-stream'
        )
        logging.info(f"Uploaded csv to s3://{bucket_name}/{s3_key} ({len(csv_bytes)} bytes)")
        return f"s3://{bucket_name}/{s3_key}"
    except Exception as e:
        logging.error(f"Failed to upload csv to S3: {e}")
        raise


def get_target_data_s3_key(
    bucket_name: str
) -> dict[str, int]:
    """Get the expected S3 key for the target data file.

    Returns:
        str: Expected S3 key (target/public/customers/LOAD00000001.parquet)
    """
    s3 = boto3.client('s3')

    prefix = 'target/'
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        contents = response.get('Contents', [])
        if contents:
            return {str(obj['Key']): int(obj['Size']) for obj in contents}
        logging.info(f"No objects found in {prefix} folder")
    except Exception as e:
        logging.error(f"Failed to list objects in {prefix} folder: {e}")
    return {}


def cleanup_s3_folders(bucket_name: str) -> None:
    """Delete source and target test folders from S3.

    Args:
        bucket_name: Name of the S3 bucket
    """
    s3 = boto3.client('s3')

    for prefix in ('source/', 'target/'):
        try:
            response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            contents = response.get('Contents', [])
            if not contents:
                logging.info(f"No objects found in {prefix} folder")
                continue

            for obj in contents:
                s3.delete_object(Bucket=bucket_name, Key=obj['Key'])
            logging.info(f"Deleted {len(contents)} objects from {prefix}")
        except Exception as e:
            logging.warning(f"Failed to delete {prefix} folder: {e}")
