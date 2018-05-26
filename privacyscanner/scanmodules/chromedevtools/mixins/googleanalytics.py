import json
from urllib.parse import parse_qs

from ..base import AbstractChromeScan


TRACKER_JS = """
JSON.stringify((function() {
    let info = {
        'was_ready': false,
        'trackers': []
    };
    ga(function() {
        info['was_ready'] = true;
        ga.getAll().forEach(function(tracker) {
            let anonymize_ip = tracker.get('anonymizeIp');
            info['trackers'].push({
                'name': tracker.get('name'),
                'tracking_id': tracker.get('trackingId'),
                'anonymize_ip': typeof(anonymize_ip) !== 'undefined' ? anonymize_ip : false
            });
        });
    });
    return info;
})());
""".lstrip()


class GoogleAnalyticsMixin(AbstractChromeScan):
    def _extract_google_analytics(self):
        ga = {}
        result = self.tab.Runtime.evaluate(expression="typeof(ga) !== 'undefined'")
        ga['has_ga_object'] = result['result']['value']
        info = json.loads(self.tab.Runtime.evaluate(expression=TRACKER_JS)['result']['value'])
        ga.update(info)

        num_requests_aip = 0
        num_requests_no_aip = 0
        for request in self.request_log:
            parsed_url = request['parsed_url']
            if self._is_google_request(parsed_url):
                qs = parse_qs(parsed_url.query)
                if 'aip' in qs and qs['aip'][-1] == '1':
                    num_requests_aip += 1
                else:
                    num_requests_no_aip += 1

        ga['anonymize'] = {
            'all_set_js': all(tracker['anonymize_ip'] for tracker in ga['trackers']), # noqa
            'num_requests_aip': num_requests_aip,
            'num_requests_no_aip': num_requests_no_aip
        }

        self.result['google_analytics'] = ga

    @staticmethod
    def _is_google_request(parsed_url):
        # Google uses stats.g.doubleclick.net for customers that have
        # enabled the Remarketing with Google Analytics feature,
        if parsed_url.netloc in ('www.google-analytics.com', 'stats.g.doubleclick.net'):
            return 'collect' in parsed_url.path or 'utm.gif' in parsed_url.path
