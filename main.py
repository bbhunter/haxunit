import subprocess

subprocess.call(["clear"])

from requests import get, post

from json import dumps, loads
import urllib3

urllib3.disable_warnings()
from subprocess import PIPE, Popen
import os
from os.path import exists
from os import mkdir, getenv
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import time
from urllib.parse import urlparse

import hashlib
import platform
import uuid

load_dotenv()
start_time = time.time()

class Colors:
    HEADER = '\033[95m'
    OK = '\033[94m'
    FAIL = '\033[91m'
    SUCCESS = '\033[92m'
    RESET = '\033[0m'
    WARNING = '\033[93m'
    BOLD = '\033[1m'


class HaxUnit:
    yes_answers = ("y", "yes", "ye")

    acunetix_email = acunetix_password = ""

    all_subdomains = []
    all_subdomains_up = []
    timestamp = datetime.now()

    anonymous_hwid = hashlib.sha256(f"{platform.system()}-{platform.node()}-{uuid.uuid4().hex}".encode()).hexdigest()

    def __init__(self, site, mode, verbose, python_bin, dir_path, iserver, itoken,
                 use_acunetix, yes_to_all, update, install_all,
                 wpscan_api_token, use_notify, cloud_upload):
        self.site = site
        self.all_subdomains.append(site)
        self.verbose = verbose
        self.quick = mode == "quick"
        self.python_bin = python_bin
        self.dir_path = dir_path
        self.yes_to_all = yes_to_all
        self.update = update
        self.install_all = install_all

        self.wpscan_api_token = wpscan_api_token or getenv("WPSCAN_API_KEY")

        self.acunetix_threshold = 30
        self.use_acunetix = use_acunetix
        self.acunetix_api_key = getenv("ACUNETIX_API_KEY")

        self.iserver = iserver
        self.itoken = itoken

        self.haxunit_api_key = getenv("HAXUNIT_API_KEY", "")
        self.use_notify = use_notify
        self.cloud_upload = cloud_upload

        self.wp_result_filenames = []

        self.cmd("clear")

        print(Colors.BOLD)
        print("""                                                                         
  _    _            _    _       _ _   
 | |  | |          | |  | |     (_) |  
 | |__| | __ ___  _| |  | |_ __  _| |_ 
 |  __  |/ _` \ \/ / |  | | '_ \| | __|
 | |  | | (_| |>  <| |__| | | | | | |_ 
 |_|  |_|\__,_/_/\_\\____/|_| |_|_|\__|

                                       v3.5 by the butcher""")

        print()

        if self.install_all:
            self.install_all_tools()
            self.print("Init", "All tools are successfully installed - good luck!", Colors.SUCCESS)
            exit()
        elif not self.site:
            self.print("Init", "Please pass a domain (-d)", Colors.FAIL)
            exit()

        print("\n[HaxUnit] Target:", site)
        print(Colors.RESET)

    @staticmethod
    def print(title: str = "", text: str = "", color_type="") -> None:
        elapsed_time = time.time() - start_time
        time_running = time.strftime("%M:%S", time.gmtime(elapsed_time))

        print(f"[{Colors.BOLD}HaxUnit{Colors.RESET}] [{time_running}] [{Colors.OK}{title}{Colors.RESET}] {color_type}{text}{Colors.RESET}")

    def cmd(self, cmd: str) -> str:
        cmd = " ".join(cmd.split())
        if self.verbose:
            self.print("CMD", cmd)
        subprocess_cmd = Popen(
            cmd,
            shell=True,
            stdout=PIPE
        )
        subprocess_return = subprocess_cmd.stdout.read().decode("utf-8").strip()
        if subprocess_return:
            print(subprocess_return)
        return subprocess_return

    def ask(self, question: str) -> bool:
        if self.yes_to_all:
            return True
        return True if input(question).lower() in self.yes_answers else False


    def read(self, file_name: str, text: bool = False) -> (str, list):
        try:
            if text:
                return "\n".join(list(set([_.strip() for _ in open(f"{self.dir_path}/{file_name}", "r").readlines()])))
            else:
                return list(set([_.strip() for _ in open(f"{self.dir_path}/{file_name}", "r").readlines()]))
        except FileNotFoundError:
            if text:
                return "FileNotFoundError"
            else:
                return []

    def write_subdomains(self, mode="a") -> None:
        with open(f"{self.dir_path}/all_subdomains.txt", mode) as f:
            all_subdomains_text = "\n".join([_ for _ in list(set(self.all_subdomains)) if _])
            f.write(all_subdomains_text)

    def httpx(self) -> None:
        self.cmd(f"httpx -l {self.dir_path}/all_subdomains.txt -fc 301,400,521 {'' if self.verbose else '-silent'} -o {self.dir_path}/httpx_result.csv -td -cdn -csv -timeout 15 {'-dashboard' if self.cloud_upload else ''}")

        awk_cmd_2 = """awk -F "," {'print $11'}"""
        self.cmd(f"cat {self.dir_path}/httpx_result.csv | {awk_cmd_2} | tail -n +2 | sort -u > {self.dir_path}/all_subdomains_up.txt")

        awk_cmd_3 = """awk -F "," {'print $22'}"""
        self.cmd(f"cat {self.dir_path}/httpx_result.csv | {awk_cmd_3} | sort -u | head -n -1 >> {self.dir_path}/httpx_ips.txt")

        self.cmd(f"cat {self.dir_path}/httpx_ips.txt {self.dir_path}/dnsx_ips.txt | sort -u > {self.dir_path}/all_ips.txt")

        self.all_subdomains_up = self.remove_unwanted_domains(self.read("all_subdomains_up.txt"))

        self.event("httpx_result", "httpx_result.csv")

    def naabu(self) -> None:
        input_file = self.read("all_subdomains.txt")

        if not input_file:
            self.print("Naabu", "all_subdomains.txt is empty - skipping")
        else:
            if self.quick:
                self.cmd(f"""
                    naabu -l {self.dir_path}/all_subdomains.txt
                     -c 100 {'' if self.verbose else '-silent'}
                     -no-color 
                     -exclude-cdn 
                     -passive
                     -ep 80,443 
                     -o {self.dir_path}/naabu_portscan.txt
                """)
            else:
                self.cmd(f"""
                    naabu -l {self.dir_path}/all_subdomains.txt
                     -c 100 {'' if self.verbose else '-silent'}
                     -no-color 
                     -top-ports 1000
                     -exclude-cdn 
                     -ep 80,443 
                     -o {self.dir_path}/naabu_portscan.txt
                """)

            self.ask_to_add(self.read("naabu_portscan.txt"))
            self.write_subdomains("w")

    def subfinder(self) -> None:
        self.print("Subfinder", "Process started")
        self.cmd(f"subfinder -d {self.site} {'' if self.verbose else '-silent'} -t 100 -nW -all -o {self.dir_path}/subfinder_subdomains.txt")
        self.ask_to_add(self.read("subfinder_subdomains.txt"))

    def nuclei(self) -> None:
        self.cmd(f"""nuclei -l {self.dir_path}/all_subdomains_up.txt
                        {"-stats" if self.verbose else "-silent "} 
                        -o {self.dir_path}/nuclei_result.txt
                        -bulk-size 100
                        -c 100
                        -no-httpx
                        -ept dns,ssl -etags detect,headers,waf,technologies,tech,wp-plugin,wordpress,whois
                        -eid robots-txt,missing-sri
                        {'-cloud-upload' if self.cloud_upload else ""} 
                        {f"-interactsh-url {self.iserver}" if self.iserver else ""}
                        {f"-itoken {self.itoken}" if self.itoken else ""}
                    """)
        self.event("nuclei_result", "nuclei_result.txt")

    def check_ip(self) -> None:
        ipaddress = get("http://ifconfig.me/ip").text
        ip_check = get(f"https://blackbox.ipinfo.app/lookup/{ipaddress}").text

        ipaddress = '.'.join(ipaddress.split('.')[:2] + ['***', '***'])
        self.print("IP Address", ipaddress)
        self.event("scan_started")

        if ip_check != "Y":
            if not self.ask(f"{Colors.WARNING}(!) Your IP ({ipaddress}) seems to be a residential/mobile IP address, would you like to continue? {Colors.RESET}"):
                exit()

    @staticmethod
    def remove_unwanted_domains(domain_list) -> list:
        unwanted_domains = (
            "cloudfront.net",
            "googleusercontent.com",
            "akamaitechnologies.com",
            "amazonaws.com",
            "salesforce-communities.com",
            "cloudflaressl.com",
            "cloudflare.net",
            "cloudflare.com",
            "transip.nl",
            "transip.eu",
            "transip.net",
            "azure-dns.com",
            "azure-dns.org",
            "azure-dns.net",
            "error"
        )

        return [_ for _ in domain_list if (not _.endswith(unwanted_domains) and not _.startswith("*"))]

    def ask_to_add(self, ask_domains: list, reask_same_tld=False) -> bool:
        ask_domains = [domain for domain in list(set(ask_domains)) if domain not in self.all_subdomains]
        ask_domains = self.remove_unwanted_domains(ask_domains)

        if ask_domains:
            print()
            for d in ask_domains:
                print(d)
            print()

            if self.ask(f"\nWould you like to add {len(ask_domains)} domains to the list? "):
                self.all_subdomains.extend(ask_domains)
                self.write_subdomains()
                return True
            elif reask_same_tld:
                self.ask_to_add(list(set([_ for _ in ask_domains if _.endswith(self.site)])))
                return True
        return False

    def dnsx_subdomains(self) -> None:
        self.print("DNSx", "Started subdomain bruteforce")
        self.cmd(f"dnsx -d {self.site} -w data/subdomains-{'1000' if self.quick else '10000'}.txt {'--stats' if not self.quick else ''} -wd {self.site} -o {self.dir_path}/dnsx_result.txt -r 8.8.8.8 -stats")
        self.ask_to_add(self.read("dnsx_result.txt"))

        if self.ask("\nWould you like to continue recursively bruteforce the found subdomains? "):
            self.print("DNSx", "Started multi-threaded recursive bruteforce")

            all_found_subdomains = []

            try:
                for iteration in range(0, 100):
                    print()
                    self.print("DNSx", f"Iteration: {iteration}")

                    def dnsx_brute(subdomain):
                        self.cmd(f"dnsx -silent -d {subdomain} -w data/subdomains-1000.txt -wd {self.site} -o {self.dir_path}/dnsx_recursive_iter_{iteration}_result.txt -r 8.8.8.8")

                    file_to_read = "dnsx_result.txt" if not iteration else f"dnsx_recursive_iter_{iteration - 1}_result.txt"
                    self.print("DNSx", f"Reading file: {file_to_read}")

                    dnsx_result = self.read(file_to_read)
                    self.print("DNSx", f"List of subdomains: {dnsx_result}")

                    if dnsx_result:
                        all_found_subdomains.extend(dnsx_result)
                        with ThreadPoolExecutor(max_workers=5) as pool:
                            pool.map(dnsx_brute, dnsx_result)
                    else:
                        break
            except KeyboardInterrupt:
                self.print("DNSx", "Bruteforce stopped")

            self.ask_to_add(all_found_subdomains)

    def dnsx_ips(self) -> None:
        self.print("DNSx", "Get A records")
        self.cmd(f"dnsx -l {self.dir_path}/all_subdomains.txt"
                 f" -a -resp-only -silent | sort -u > {self.dir_path}/dnsx_ips.txt")

        # self.ask_to_add(self.read("dnsx_ips.txt"))

    def acunetix(self) -> None:

        def acunetix_up():
            try:
                get("https://localhost:3443/api/v1/target_groups")
                return True
            except ConnectionError:
                return False

        if self.use_acunetix and self.acunetix_api_key and acunetix_up():
            self.print("Acunetix", "Starting acunetix")
            self.event("using_acunetix")

            data = {}
            cookies = {'ui_session': self.acunetix_api_key}
            headers = {'x-auth': self.acunetix_api_key, 'Content-Type': 'application/json'}

            print()
            for d in self.all_subdomains_up:
                print(d)
            print()

            self.print("Acunetix", f"Active subdomain count: {len(self.all_subdomains_up)}")

            all_groups = get("https://localhost:3443/api/v1/target_groups", headers=headers, verify=False).json()["groups"]

            try:
                group_id = next(row["group_id"] for row in all_groups if row["name"] == self.site)
            except StopIteration:
                group_id = None

            if group_id:
                self.print("Acunetix", f"Group already exists: {group_id}")
            else:
                self.print("Acunetix", "Creating new group")

                group_id = post(
                    'https://localhost:3443/api/v1/target_groups',
                    headers=headers,
                    cookies=cookies,
                    data=dumps({"name": self.site, "description": ""}),
                    verify=False
                ).json()["group_id"]

            if len(self.all_subdomains_up) < self.acunetix_threshold and self.ask(
                    "[HaxUnit] Do you want to scan all subdomains using acunetix? "):
                data = {
                    "targets": [{
                        "address": subdomain,
                        "description": ""
                    } for subdomain in self.all_subdomains_up],
                    "groups": [group_id]
                }
            elif self.ask("[HaxUnit] Do you want to scan only the main domain using acunetix? "):
                main_domain = [_ for _ in self.all_subdomains_up if f"//{self.site}" in _][0]
                self.print("Acunetix", f"Main domain: {main_domain}")
                data = {
                    "targets": [{
                        "address": main_domain,
                        "description": ""
                    }],
                    "groups": [group_id]
                }

            if data:

                response = post('https://localhost:3443/api/v1/targets/add', headers=headers, cookies=cookies,
                                data=dumps(data), verify=False).json()

                for target in response["targets"]:
                    data = {
                        "profile_id": "11111111-1111-1111-1111-111111111111",
                        "ui_session_id": "56eeaf221a345258421fd6ae1acca394",
                        "incremental": False,
                        "schedule": {
                            "disable": False,
                            "start_date": None,
                            "time_sensitive": False
                        },
                        "target_id": target["target_id"]
                    }

                    post('https://localhost:3443/api/v1/scans', headers=headers, cookies=cookies, data=dumps(data),
                         verify=False)

                self.print("Acunetix", f"Scan(s) started!")

    def katana(self) -> None:
        self.cmd(f"katana -list {self.dir_path}/all_subdomains.txt {'-d 1' if self.quick else ''} | unfurl format %d:%P | sed 's/:$//g' | sort -u > {self.dir_path}/katana_domains.txt")
        self.ask_to_add(self.read("katana_domains.txt"))

    def ripgen(self):
        self.cmd(f"ripgen -d {self.dir_path}/all_subdomains.txt | sort -u | dnsx -silent > {self.dir_path}/ripgen_result.txt")
        self.ask_to_add(self.read("ripgen_result.txt"))

    def notify(self):
        if self.use_notify:
            self.event("using_notify")

            def get_severity_emoji(severity):
                severity_mapping = {
                    'info': '🟢',
                    'low': '🟡',
                    'medium': '🟠',
                    'high': '🔴',
                    'critical': '🚨',
                    'unknown': '❓'
                }
                return severity_mapping.get(severity.lower(), '❓')

            def transform_label(label):
                return ' '.join(word.capitalize() for word in label.replace('-', ' ').split())

            def add_emojis_and_format(result):
                formatted_lines = []
                for line in result.strip().split('\n'):
                    parts = line.split()
                    if len(parts) < 4:
                        formatted_lines.append(f"❓ {line}")
                        continue
                    label, protocol, severity, rest = parts[0].strip('[]'), parts[1].strip('[]'), parts[2].strip(
                        '[]'), ' '.join(parts[3:])
                    label_parts = label.split(':')
                    label_main = transform_label(label_parts[0])
                    label_sub = f": {transform_label(label_parts[1])}" if len(label_parts) > 1 else ''
                    emoji = get_severity_emoji(severity)
                    formatted_lines.append(f"{emoji} | {label_main}{label_sub} - {protocol.upper()} | {rest}")
                return '\n'.join(formatted_lines)

            with open(f"{self.dir_path}/nuclei_result.txt", "r") as f:
                nuclei_result = f.read()

            use_local_config = "-provider-config notify-config.yaml" if exists("notify-config.yaml") else ""

            self.cmd(f'echo "[$(date +"%Y-%m-%d")] Finished scan for these hosts:" | notify -silent {use_local_config}')

            self.cmd(f"notify -i {self.dir_path}/all_subdomains_up.txt -silent -bulk {use_local_config}")
            self.cmd(f"""notify -silent {use_local_config} <<< "$(echo -e '```'$(cat {self.dir_path}/all_subdomains_up.txt)'```')" """)

            self.cmd(f'echo "[$(date +"%Y-%m-%d")] Nuclei results:" | notify -silent {use_local_config}')

            if nuclei_result:
                with open(f"{self.dir_path}/nuclei_result_formatted.txt", "w", encoding='utf-8') as f:
                    f.write(add_emojis_and_format(nuclei_result))

                self.cmd(f"notify -i {self.dir_path}/nuclei_result_formatted.txt -bulk -silent {use_local_config}")

                if any(sev in nuclei_result for sev in ['high', 'critical']):
                    self.cmd(f'echo "⚠️ ️High severity issues found <!channel>" | notify -silent {use_local_config}')
                elif any(sev in nuclei_result for sev in ['low', 'medium']):
                    self.cmd(f'echo "⚠️ Medium/Low severity issues found <!channel>" | notify -silent {use_local_config}')
            else:
                self.cmd(f'echo "✅ No results" | notify -silent {use_local_config}')

            if self.wp_result_filenames:
                self.cmd(f'echo "[$(date +"%Y-%m-%d")] WPScan results:" | notify -silent {use_local_config}')
                for wp_result_filename in self.wp_result_filenames:
                    self.cmd(f"notify -i {self.dir_path}/{wp_result_filename} -bulk -silent {use_local_config}")

    def event(self, message=None, filename=None):
        try:
            url = "https://app.haxunit.com/handle_event"

            json_data = {
                "domain": self.site,
                "message": message,
                "hwid": self.anonymous_hwid,
                "api_key": self.haxunit_api_key
            }

            if filename:
                json_data["filename"] = filename
                with open(f'{self.dir_path}/{filename}', 'rb', encoding="utf-8") as file:
                    post(url, data=json_data, files={'file': file})
            else:
                post(url, data=json_data)
        except: pass

    def droopescan(self):
        pass

    def wpscan(self):

        def single_wpscan(wp_domain):
            filename = wp_domain.replace("https://", "").replace("http://", "").replace(".", "_").replace("/", "").replace(":", "_").strip()
            self.cmd(f"docker run -it --rm wpscanteam/wpscan --update --url {wp_domain} {f'--api-token {self.wpscan_api_token}' if self.wpscan_api_token else ''} --ignore-main-redirect --disable-tls-checks >> {self.dir_path}/wpscan_{filename}.txt")
            self.wp_result_filenames.append(f"wpscan_{filename}.txt")

        self.cmd(f"grep WordPress {self.dir_path}/httpx_result.csv | awk -F ',' {{'print $11'}} | sort -u > {self.dir_path}/wordpress_domains.txt")
        wordpress_domains = self.read("wordpress_domains.txt")

        if wordpress_domains:
            for domain in wordpress_domains:
                print(domain)
            print()

            if self.ask(f"Would you like to run wpscan on all ({len(wordpress_domains)}) domains? "):
                self.event("using_wpscan")

                with ThreadPoolExecutor(max_workers=5) as pool:
                    pool.map(single_wpscan, wordpress_domains)

    def install_wpscan(self):
        self.cmd("docker pull wpscanteam/wpscan")

    def install_ripgen(self):
        for rg_cmd in (
            "sudo apt remove rustc -y",
            "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sudo sh -s -- -y",
            "export PATH='/root/.cargo/bin:${PATH}'",
            "sudo apt install cargo -y",
            "cargo install ripgen",
            'echo "export PATH=$PATH:$HOME/.cargo/bin" >> ~/.bashrc',
        ):
            self.cmd(rg_cmd)

    def install_all_tools(self):

        self.install_ripgen()
        self.install_wpscan()

        self.print("Installer", "Installing gau")
        for text, cmd in (
                (f"Downloading gau", f"wget https://github.com/lc/gau/releases/download/v2.2.3/gau_2.2.3_linux_amd64.tar.gz --quiet"),
                ("Extracting tar.gz", f"tar xf gau_2.2.3_linux_amd64.tar.gz"),
                (f"Moving gau to bin", f"sudo mv gau /usr/local/bin/gau"),
                ("Cleanup", f"rm -f gau_2.2.3_linux_amd64.tar.gz README.md LICENSE.md LICENSE")
        ):
            if text and cmd:
                self.cmd(cmd)

        for cmd_tool in (
                "go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest",
                "go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest",
                "sudo apt install -y libpcap-dev",
                "go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest",
                "go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest",
                "go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
                "nuclei -update-templates",
                "go install github.com/lc/gau/v2/cmd/gau@latest",
                "go install github.com/tomnomnom/unfurl@latest",
                "go install -v github.com/projectdiscovery/notify/cmd/notify@latest",
        ):
            self.cmd(cmd_tool)


def script_init(args) -> str:
    """Create scans folder, workspace and the current scan folder"""

    if not args.domain:
        return ""

    # Create 'scans' folder if it doesn't exist
    scans_folder = "scans"
    if not exists(scans_folder):
        mkdir(scans_folder)

    # Create domain-specific folder if it doesn't exist
    domain_folder = os.path.join(scans_folder, args.domain)
    if not exists(domain_folder):
        mkdir(domain_folder)

    # Create timestamped scan folder
    scan_folder = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    dir_path = os.path.join(domain_folder, scan_folder)
    mkdir(dir_path)

    return dir_path


def main():
    parser = argparse.ArgumentParser(description='HaxUnit')
    parser.add_argument('-d', '--domain', type=str, help='the website to recon: example.com')
    parser.add_argument('-m', '--mode', type=str, choices=['quick', 'extensive'], help='set scan mode', default='quick')
    parser.add_argument('-v', '--verbose', action='store_true', help='print more information', default=True)
    parser.add_argument('-b', '--bin', type=str, help='set which python bin to use', default='python3')
    parser.add_argument('-is', '--iserver', type=str, help='interactsh server URL for self-hosted instance', default='')
    parser.add_argument('-it', '--itoken', type=str, help='authentication token for self-hosted interactsh server', default='')
    parser.add_argument('-acu', '--use-acunetix', action='store_true', help='Acunetix API key', default='')
    parser.add_argument('-y', '--yes', action='store_true', help='yes to all')
    parser.add_argument('-u', '--update', action='store_true', help='update all tools')
    parser.add_argument('-i', '--install', action='store_true', help='install all tools')
    parser.add_argument('--wpscan-api-token', type=str, help='The WPScan API Token to display vulnerability data', default='')
    parser.add_argument('--use-notify', action='store_true', help='Run notify on completion')
    parser.add_argument('--cloud-upload', action='store_true', help='Upload results to ProjectDiscovery cloud')

    args = parser.parse_args()

    if args.domain:
        parse_result = urlparse(args.domain)
        args.domain = parse_result.netloc if parse_result.netloc else parse_result.path

    dir_path = script_init(args)

    hax = HaxUnit(
        site=args.domain,
        mode=args.mode,
        verbose=args.verbose,
        python_bin=args.bin,
        dir_path=dir_path,
        iserver=args.iserver,
        itoken=args.itoken,
        use_acunetix=args.use_acunetix,
        yes_to_all=args.yes,
        update=args.update,
        install_all=args.install,
        wpscan_api_token=args.wpscan_api_token,
        use_notify=args.use_notify,
        cloud_upload=args.cloud_upload,
    )

    try:
        hax.check_ip()
        hax.dnsx_subdomains()
        hax.subfinder()
        hax.katana()
        hax.ripgen()
        hax.dnsx_ips()
        hax.naabu()
        hax.httpx()
        hax.wpscan()
        hax.acunetix()
        hax.nuclei()
        hax.notify()

        print(f"\ncd {dir_path}\n")
    except KeyboardInterrupt:
        print(f"[{Colors.BOLD}HaxUnit{Colors.RESET}] [{Colors.OK}KeyboardInterrupt{Colors.RESET}] {Colors.WARNING}Aborted{Colors.RESET}")


if __name__ == '__main__':
    main()
