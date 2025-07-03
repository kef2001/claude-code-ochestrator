"""
Feature Flag CLI - Simple command-line interface for managing feature flags
"""

import argparse
import sys
import json
from typing import Optional
from .feature_flags import FeatureFlagManager, FlagType


class FeatureFlagCLI:
    """Command-line interface for feature flags"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.manager = FeatureFlagManager(config_path)
    
    def create_flag(self, name: str, enabled: bool = False, value: str = None, 
                   description: str = "", flag_type: str = "boolean"):
        """Create a new feature flag"""
        try:
            # Parse value based on type
            parsed_value = self._parse_value(value, flag_type)
            flag_type_enum = FlagType(flag_type)
            
            self.manager.create_flag(
                name=name,
                enabled=enabled,
                value=parsed_value,
                description=description,
                flag_type=flag_type_enum
            )
            print(f"Created flag '{name}' (enabled: {enabled})")
        except Exception as e:
            print(f"Error creating flag: {e}")
            sys.exit(1)
    
    def update_flag(self, name: str, enabled: Optional[bool] = None, 
                   value: Optional[str] = None, description: Optional[str] = None):
        """Update an existing feature flag"""
        try:
            # Get current flag to determine type for value parsing
            current_flag = self.manager.storage.get_flag(name)
            if current_flag and value is not None:
                parsed_value = self._parse_value(value, current_flag.flag_type.value)
            else:
                parsed_value = value
            
            success = self.manager.update_flag(
                name=name,
                enabled=enabled,
                value=parsed_value,
                description=description
            )
            if success:
                print(f"Updated flag '{name}'")
            else:
                print(f"Flag '{name}' not found")
                sys.exit(1)
        except Exception as e:
            print(f"Error updating flag: {e}")
            sys.exit(1)
    
    def delete_flag(self, name: str):
        """Delete a feature flag"""
        try:
            success = self.manager.delete_flag(name)
            if success:
                print(f"Deleted flag '{name}'")
            else:
                print(f"Flag '{name}' not found")
                sys.exit(1)
        except Exception as e:
            print(f"Error deleting flag: {e}")
            sys.exit(1)
    
    def list_flags(self):
        """List all feature flags"""
        try:
            flags = self.manager.list_flags()
            if not flags:
                print("No feature flags found")
                return
            
            print(f"Found {len(flags)} feature flag(s):")
            print("-" * 80)
            for name, flag_data in flags.items():
                enabled = "✓" if flag_data["enabled"] else "✗"
                print(f"{enabled} {name} ({flag_data['flag_type']})")
                if flag_data["description"]:
                    print(f"    Description: {flag_data['description']}")
                if flag_data["value"] is not None:
                    print(f"    Value: {flag_data['value']}")
                print()
        except Exception as e:
            print(f"Error listing flags: {e}")
            sys.exit(1)
    
    def get_flag(self, name: str):
        """Get a specific feature flag"""
        try:
            flag = self.manager.storage.get_flag(name)
            if flag is None:
                print(f"Flag '{name}' not found")
                sys.exit(1)
            
            enabled = "✓" if flag.enabled else "✗"
            print(f"{enabled} {flag.name} ({flag.flag_type.value})")
            if flag.description:
                print(f"Description: {flag.description}")
            if flag.value is not None:
                print(f"Value: {flag.value}")
        except Exception as e:
            print(f"Error getting flag: {e}")
            sys.exit(1)
    
    def check_flag(self, name: str):
        """Check if a flag is enabled"""
        try:
            enabled = self.manager.is_enabled(name)
            print(f"Flag '{name}' is {'enabled' if enabled else 'disabled'}")
        except Exception as e:
            print(f"Error checking flag: {e}")
            sys.exit(1)
    
    def _parse_value(self, value: str, flag_type: str):
        """Parse value based on flag type"""
        if value is None:
            return None
        
        if flag_type == "boolean":
            return value.lower() in ("true", "1", "yes", "on")
        elif flag_type == "number":
            try:
                return float(value) if '.' in value else int(value)
            except ValueError:
                raise ValueError(f"Invalid number value: {value}")
        elif flag_type == "json":
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON value: {value}")
        else:  # string
            return value


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Feature Flag Management CLI")
    parser.add_argument("--config", help="Path to feature flags config file")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create flag
    create_parser = subparsers.add_parser("create", help="Create a new feature flag")
    create_parser.add_argument("name", help="Flag name")
    create_parser.add_argument("--enabled", action="store_true", help="Enable the flag")
    create_parser.add_argument("--value", help="Flag value")
    create_parser.add_argument("--description", default="", help="Flag description")
    create_parser.add_argument("--type", choices=["boolean", "string", "number", "json"], 
                              default="boolean", help="Flag type")
    
    # Update flag
    update_parser = subparsers.add_parser("update", help="Update an existing feature flag")
    update_parser.add_argument("name", help="Flag name")
    update_parser.add_argument("--enabled", type=bool, help="Enable/disable the flag")
    update_parser.add_argument("--value", help="Flag value")
    update_parser.add_argument("--description", help="Flag description")
    
    # Delete flag
    delete_parser = subparsers.add_parser("delete", help="Delete a feature flag")
    delete_parser.add_argument("name", help="Flag name")
    
    # List flags
    list_parser = subparsers.add_parser("list", help="List all feature flags")
    
    # Get flag
    get_parser = subparsers.add_parser("get", help="Get a specific feature flag")
    get_parser.add_argument("name", help="Flag name")
    
    # Check flag
    check_parser = subparsers.add_parser("check", help="Check if a flag is enabled")
    check_parser.add_argument("name", help="Flag name")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    cli = FeatureFlagCLI(args.config)
    
    if args.command == "create":
        cli.create_flag(
            name=args.name,
            enabled=args.enabled,
            value=args.value,
            description=args.description,
            flag_type=args.type
        )
    elif args.command == "update":
        cli.update_flag(
            name=args.name,
            enabled=args.enabled,
            value=args.value,
            description=args.description
        )
    elif args.command == "delete":
        cli.delete_flag(args.name)
    elif args.command == "list":
        cli.list_flags()
    elif args.command == "get":
        cli.get_flag(args.name)
    elif args.command == "check":
        cli.check_flag(args.name)


if __name__ == "__main__":
    main()