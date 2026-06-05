# KARTE DICOM Preprocessor

## 目的

KARTE Ph1で検証する、匿名化済みDICOMからKARTEアップロード用の構造化JPG ZIPを作成する最小CLIプロトタイプです。

DICOM原本をKARTE本体へ直接取り込まず、ローカルでStudy / Series / Image相当の構造を保ったJPG群と`metadata.json`を作成します。

このツールは診断用DICOMビューアではありません。KARTEアップロード仕様を固めるためのローカル変換ツールです。

## インストール方法

Python 3.10以上を推奨します。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 使い方

必須オプションは`--input`と`--output`です。

```bash
python karte_dicom_preprocessor.py \
  --input data/anonymized_petct_case \
  --output outputs/karte_upload_test \
  --display-width 1024 \
  --thumb-size 256 \
  --zip
```

## --list-series の例

フォルダ構造には依存せず、DICOMタグからStudy / Seriesを再構成して一覧表示します。

```bash
python karte_dicom_preprocessor.py \
  --input data/anonymized_petct_case \
  --output outputs/karte_upload_test \
  --list-series
```

表示項目:

- Series番号
- Modality
- SeriesDescription
- BodyPartExamined
- ImageType
- 画像枚数
- InstanceNumberの範囲
- ImagePositionPatientの有無
- SliceLocationの有無
- 推定sort_method

## --include-series を使った変換例

`--list-series`で確認したSeries番号を指定して変換します。

```bash
python karte_dicom_preprocessor.py \
  --input data/anonymized_petct_case \
  --output outputs/karte_upload_test \
  --include-series 1,2,3 \
  --display-width 1024 \
  --thumb-size 256 \
  --zip
```

## --series-labels で患者向け表示名を指定する例

DICOMの`SeriesDescription`が患者向け表示名として不十分な場合、`--list-series`で確認したSeries番号ごとに表示名を指定できます。

```bash
python karte_dicom_preprocessor.py \
  --input data/anonymized_petct_case \
  --output outputs/karte_upload_test \
  --include-series 2,3,4,5,7,8,9,10 \
  --series-labels "2:胸部CT肺野条件,3:胸部CT縦隔条件,4:全身CT横断像,5:全身PET横断像,7:Fusion横断像,8:Fusion冠状断,9:Fusion矢状断,10:PET-MIP回転像" \
  --zip
```

指定した表示名は`metadata.json`の各series要素に`patient_display_name`として保存されます。日本語の表示名はフォルダ名には使わず、フォルダ名は従来通り安全な英数字ベースで作成します。未指定のSeriesでは`series_description_sanitized`または`series_name`をfallbackとして使用します。

## 出力構造

```text
KARTE_UPLOAD_<study_hash>/
  metadata.json
  series_001_CT_CT_axial/
    display/
      0001.jpg
      0002.jpg
    thumb/
      0001.jpg
      0002.jpg
KARTE_UPLOAD_<study_hash>.zip
```

`metadata.json`にはStudyInstanceUID / SeriesInstanceUIDの元値を保存せず、sha256 hashのみ保存します。PatientName、PatientID、PatientBirthDate、AccessionNumber、ReferringPhysicianName、InstitutionName、SOPInstanceUIDも保存しません。

## 注意事項

- 入力対象は匿名化済みDICOMのみです。
- DICOMタグ匿名化、焼き込み文字除去、SUV計算、MPR/MIP再構成、診断用画質保証は対象外です。
- 生成JPGはKARTEアップロード仕様検証用であり、診断用途には使用しません。
- DICOM原本、生成JPG、生成ZIPをGit管理しないでください。
- `data/`、`*.dcm`、`*.jpg`、`*.zip`は`.gitignore`で除外します。
