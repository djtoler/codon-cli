#!/usr/bin/env python3
"""
SAOP Server Banner Generator
Creates a beautiful ASCII art banner for your SAOP server startup
"""

def create_saop_banner(
    agent_name="FunnyAgent",
    docs_url="https://saop.ai/docs",
    saop_version="0.1"
):
    """Generate a SAOP banner with custom server details"""
    
    # Box drawing characters
    top_border = "╮"
    bottom_border = "╯"
    side = "│"
    horizontal = "─"
    
    # ASCII art for SAOP - big block letters
    ascii_art = [
        "     _____ _____ _____ _____",
        "    |   __|  _  |   __|  _  |",
        "    |__   |     |   __|   __|", 
        "    |_____|__|__|_____|__|  ",
        "",
        "    Standardised Agent Orchestration Platform"
    ]
    
    # Calculate width 
    width = 76
    
    # Create the banner
    banner_lines = []
    
    # Top border with title
    banner_lines.append(f"{horizontal} SAOP {horizontal * (width - 7)}{top_border}")
    
    # Empty line
    banner_lines.append(f"{side}{' ' * width}{side}")
    
    # ASCII art - center it
    for line in ascii_art:
        # Center the ASCII art
        padding = (width - len(line)) // 2
        padded_line = (' ' * padding + line).ljust(width)
        banner_lines.append(f"{side}{padded_line}{side}")
    
    # Empty lines
    banner_lines.append(f"{side}{' ' * width}{side}")
    banner_lines.append(f"{side}{' ' * width}{side}")
    
    # Server information
    info_lines = [
        f"    🤖 Agent name:       {agent_name}",
        f"    📚 Docs URL:         {docs_url}",
        f"    🤝 SAOP Version:     {saop_version}",
    ]
    
    for line in info_lines:
        padded_line = line.ljust(width)
        banner_lines.append(f"{side}{padded_line}{side}")
    
    # Empty line
    banner_lines.append(f"{side}{' ' * width}{side}")
    
    # Bottom border
    banner_lines.append(f"╰{horizontal * width}{bottom_border}")
    
    return "\n".join(banner_lines)


def create_saop_banner_v2(
    agent_name="FunnyAgent",
    docs_url="https://saop.ai/docs", 
    saop_version="0.1"
):
    """Alternative SAOP banner with bigger, more stylized ASCII art"""
    
    # Box drawing characters
    top_border = "╮"
    bottom_border = "╯"
    side = "│"
    horizontal = "─"
    
    # Bigger ASCII art for SAOP
    ascii_art = [
        "    ░██████╗ ░█████╗░ ░█████╗░ ██████╗░",
        "    ██╔════╝ ██╔══██╗ ██╔══██╗ ██╔══██╗",
        "    ╚█████╗░ ███████║ ██║  ██║ ██████╔╝",
        "    ░╚═══██╗ ██╔══██║ ██║  ██║ ██╔═══╝░",
        "    ██████╔╝ ██║  ██║ ╚█████╔╝ ██║     ",
        "    ╚═════╝░ ╚═╝  ╚═╝ ░╚════╝░ ╚═╝     ",
        "",
        "      Standardised Agent Orchestration Platform"
    ]
    
    width = 76
    banner_lines = []
    
    # Top border
    banner_lines.append(f"{horizontal} Codon {horizontal * (width - 7)}{top_border}")
    
    # Empty line
    banner_lines.append(f"{side}{' ' * width}{side}")
    
    # ASCII art
    for line in ascii_art:
        # Center the line
        padding = max(0, (width - len(line)) // 2)
        padded_line = (' ' * padding + line).ljust(width)
        banner_lines.append(f"{side}{padded_line}{side}")
    
    # Empty lines
    banner_lines.append(f"{side}{' ' * width}{side}")
    banner_lines.append(f"{side}{' ' * width}{side}")
    
    # Server information
    info_lines = [
        f"    🤖 Agent name:       {agent_name}",
        f"    📚 Docs URL:         {docs_url}", 
        f"    🤝 SAOP Version:     {saop_version}",
    ]
    
    for line in info_lines:
        padded_line = line.ljust(width)
        banner_lines.append(f"{side}{padded_line}{side}")
    
    # Empty line
    banner_lines.append(f"{side}{' ' * width}{side}")
    
    # Bottom border
    banner_lines.append(f"╰{horizontal * width}{bottom_border}")
    
    return "\n".join(banner_lines)


def print_saop_banner(version=1, **kwargs):
    """Print the SAOP banner to console"""
    if version == 2:
        banner = create_saop_banner_v2(**kwargs)
    else:
        banner = create_saop_banner(**kwargs)
    print(banner)


# Class for integration
class SAOPBanner:
    """Class to handle banner generation for SAOP servers"""
    
    @staticmethod
    def show_startup_banner(config, style=1):
        """Show banner on server startup"""
        if style == 2:
            banner = create_saop_banner_v2(
                agent_name=config.get('agent_name', 'DefaultAgent'),
                docs_url=config.get('docs_url', 'https://saop.ai/docs'),
                saop_version=config.get('saop_version', '0.1')
            )
        else:
            banner = create_saop_banner(
                agent_name=config.get('agent_name', 'DefaultAgent'),
                docs_url=config.get('docs_url', 'https://saop.ai/docs'),
                saop_version=config.get('saop_version', '0.1')
            )
        print(banner)
        print()


# Example usage
if __name__ == "__main__":
    print("SAOP Banner Style 1:")
    print_saop_banner(
        agent_name="FunnyAgent",
        docs_url="https://saop.ai/docs", 
        saop_version="0.1"
    )
    
    print("\n" + "="*80 + "\n")
    
    print("SAOP Banner Style 2 (Fancy Unicode):")
    print_saop_banner(
        version=2,
        agent_name="FunnyAgent",
        docs_url="https://saop.ai/docs",
        saop_version="0.1"
    )
    
    print("\n" + "="*80 + "\n")
    
    print("Custom Example:")
    print_saop_banner(
        agent_name="SuperBot",
        docs_url="https://my-saop-docs.com",
        saop_version="1.0.0"
    )


def start_saop_baner():
    config = {
        'agent_name': 'FunnyAgent',
        'docs_url': 'https://saop.ai/docs',
        'saop_version': '0.1'
    }

    print("✅ SAOP agent ready!")
    SAOPBanner.show_startup_banner(config, style=2)