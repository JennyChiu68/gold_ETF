#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
INPUT_HTML="$ROOT_DIR/index.html"
OUTPUT_HTML="$ROOT_DIR/gold_etf_demo_single.html"
HISTORY_BUNDLE="$ROOT_DIR/data/spdr_gld_5y_history.bundle.js"
QUOTE_BUNDLE="$ROOT_DIR/data/offshore_cnh_quote.bundle.js"

perl -e '
  use strict;
  use warnings;

  my ($input_path, $history_path, $quote_path, $output_path) = @ARGV;

  sub slurp {
    my ($path) = @_;
    open my $fh, "<", $path or die "open $path failed: $!";
    local $/;
    return <$fh>;
  }

  my $html = slurp($input_path);
  my $history = slurp($history_path);
  my $quote = slurp($quote_path);

  $html =~ s{<script src="data/spdr_gld_5y_history.bundle.js"></script>}{<script>\n$history\n</script>}s;
  $html =~ s{<script src="data/offshore_cnh_quote.bundle.js"></script>}{<script>\n$quote\n</script>}s;

  open my $out, ">", $output_path or die "write $output_path failed: $!";
  print {$out} $html;
' "$INPUT_HTML" "$HISTORY_BUNDLE" "$QUOTE_BUNDLE" "$OUTPUT_HTML"

printf 'Built %s\n' "$OUTPUT_HTML"
