#
# Support library for script talking to the Frikanalen API
#

package Frikanalen::API;
require Exporter;

use JSON;
use LWP::Simple;

our $VERSION = 0.01;
our @ISA     = qw(Exporter);
our @EXPORT  = qw(
                  parse_duration
                  process_videos
                  );

my $videosurl = 'http://beta.frikanalen.tv/api/videos/';

# Convert "04:05.12" to 4 * 60 + 5.12
sub parse_duration {
    my $durationstr = shift;
    my @parts = split(/:/, $durationstr);
    my $duration = 0;
    while (my $part = shift @parts) {
        $duration *= 60;
        $duration += int($part);
    }
#    print "$durationstr = $duration\n";
    return $duration;
}

sub process_videos {
    my ($callback, $callbackdata, $query) = @_;
    print $callback;
    my $count = 0;
    my $url = $videosurl;
    while ($url) {
        if (defined $query) {
            $url .= "?1=$query";
        }

        my $jsonstr = get($url);
        my $json = decode_json( $jsonstr );
        unless ($json->{'results'}) {
            return undef;
        }
        foreach my $video (@{$json->{'results'}}) {
            $count++ if &$callback($video, $callbackdata);
        }
        if (defined $json->{'next'}) {
            $url = $json->{'next'};
        } else {
            $url = undef;
        }
    }
    return $count;

}

1;
