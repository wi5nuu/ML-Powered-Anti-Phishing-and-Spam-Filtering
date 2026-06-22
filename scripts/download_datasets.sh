#!/bin/bash
set -euo pipefail

mkdir -p data/raw/enron data/raw/spamassassin_corpus data/raw/indonesian

echo "==> Downloading SpamAssassin public corpus..."
wget -q -O data/raw/spamassassin_corpus/spam_2.tar.bz2 \
  https://spamassassin.apache.org/old/publiccorpus/20030228_spam_2.tar.bz2
wget -q -O data/raw/spamassassin_corpus/easy_ham.tar.bz2 \
  https://spamassassin.apache.org/old/publiccorpus/20030228_easy_ham.tar.bz2
wget -q -O data/raw/spamassassin_corpus/hard_ham.tar.bz2 \
  https://spamassassin.apache.org/old/publiccorpus/20030228_hard_ham.tar.bz2

echo "==> Extracting..."
tar -xjf data/raw/spamassassin_corpus/spam_2.tar.bz2 -C data/raw/spamassassin_corpus/
tar -xjf data/raw/spamassassin_corpus/easy_ham.tar.bz2 -C data/raw/spamassassin_corpus/
tar -xjf data/raw/spamassassin_corpus/hard_ham.tar.bz2 -C data/raw/spamassassin_corpus/

echo "==> Downloading Indonesian SMS spam dataset..."
wget -q -O data/raw/indonesian/dataset_sms_spam_v2.csv \
  "https://gist.githubusercontent.com/agtbaskara/a1a7017027cc1df9d35cf06e1e5575b7/raw/dataset_sms_spam_v2.csv"

echo "✅ Dataset download selesai."
echo "   Catatan: Dataset Enron harus didownload manual dari:"
echo "   https://www2.aueb.gr/users/ion/data/enron-spam/"
echo "   Simpan ke: data/raw/enron/"
