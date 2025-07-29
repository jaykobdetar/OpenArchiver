#!/usr/bin/env python3

import click
import sys
import json
from pathlib import Path
from datetime import datetime

from src.models import Archive, Profile, MetadataField, FieldType
from src.core import FileIngestionService, IndexingService, SearchService, IntegrityService, ExportService


@click.group()
def cli():
    """Archive Tool - Build large-scale, self-contained archives"""
    pass


@cli.command()
@click.argument('path', type=click.Path())
@click.option('--name', '-n', required=True, help='Archive name')
@click.option('--description', '-d', default='', help='Archive description')
def create(path, name, description):
    """Create a new archive"""
    archive_path = Path(path)
    
    try:
        archive = Archive(archive_path)
        archive.create(name, description)
        click.echo(f"Created archive '{name}' at {archive_path}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('archive_path', type=click.Path(exists=True))
def info(archive_path):
    """Show archive information"""
    try:
        archive = Archive(Path(archive_path))
        archive.load()
        
        click.echo(f"Archive: {archive.config.name}")
        click.echo(f"ID: {archive.config.id}")
        click.echo(f"Description: {archive.config.description}")
        click.echo(f"Created: {archive.config.created_at}")
        click.echo(f"Updated: {archive.config.updated_at}")
        click.echo(f"Path: {archive.root_path}")
        
        # Get statistics
        indexing = IndexingService(archive)
        stats = indexing.get_statistics()
        
        click.echo(f"\nStatistics:")
        click.echo(f"  Total assets: {stats['total_assets']}")
        click.echo(f"  Total size: {stats['total_size']:,} bytes")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('archive_path', type=click.Path(exists=True))
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--profile', '-p', help='Profile ID to use')
def add(archive_path, file_path, profile):
    """Add a file to the archive"""
    try:
        archive = Archive(Path(archive_path))
        archive.load()
        
        ingestion = FileIngestionService(archive)
        indexing = IndexingService(archive)
        
        # Load profile if specified
        profile_obj = None
        if profile:
            profile_path = archive.profiles_path / f"{profile}.json"
            if profile_path.exists():
                profile_obj = Profile.load_from_file(profile_path)
        
        # Ingest file
        file_to_add = Path(file_path)
        if file_to_add.is_file():
            asset = ingestion.ingest_file(file_to_add, profile=profile_obj)
            indexing.index_asset(asset)
            click.echo(f"Added file: {asset.metadata.asset_id}")
        elif file_to_add.is_dir():
            assets = ingestion.ingest_directory(file_to_add, profile=profile_obj)
            for asset in assets:
                indexing.index_asset(asset)
            click.echo(f"Added {len(assets)} files from directory")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('archive_path', type=click.Path(exists=True))
@click.option('--query', '-q', help='Search query')
@click.option('--limit', '-l', default=10, help='Maximum results to show')
def search(archive_path, query, limit):
    """Search the archive"""
    try:
        archive = Archive(Path(archive_path))
        archive.load()
        
        search_service = SearchService(archive)
        results, total = search_service.search(query=query, limit=limit)
        
        click.echo(f"Found {total} results (showing {len(results)}):")
        
        for result in results:
            click.echo(f"  {result.asset_id}: {result.file_name}")
            click.echo(f"    Path: {result.archive_path}")
            click.echo(f"    Size: {result.file_size:,} bytes")
            if result.mime_type:
                click.echo(f"    Type: {result.mime_type}")
            click.echo()
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('archive_path', type=click.Path(exists=True))
def verify(archive_path):
    """Verify archive integrity"""
    try:
        archive = Archive(Path(archive_path))
        archive.load()
        
        integrity = IntegrityService(archive)
        
        def progress_callback(current, total, message):
            click.echo(f"Progress: {current}/{total} - {message}")
        
        integrity.set_progress_callback(progress_callback)
        report = integrity.verify_all()
        
        click.echo(f"\nIntegrity Report:")
        click.echo(f"  Total assets: {report.total_assets}")
        click.echo(f"  Verified: {report.verified_assets}")
        click.echo(f"  Corrupted: {len(report.corrupted_assets)}")
        click.echo(f"  Missing: {len(report.missing_assets)}")
        click.echo(f"  Success rate: {report.success_rate:.1f}%")
        click.echo(f"  Duration: {report.duration:.1f} seconds")
        
        if report.corrupted_assets:
            click.echo("\nCorrupted files:")
            for path in report.corrupted_assets:
                click.echo(f"  {path}")
        
        if report.missing_assets:
            click.echo("\nMissing files:")
            for path in report.missing_assets:
                click.echo(f"  {path}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('archive_path', type=click.Path(exists=True))
@click.argument('output_path', type=click.Path())
@click.option('--format', '-f', type=click.Choice(['bagit', 'directory']), default='bagit', help='Export format')
def export(archive_path, output_path, format):
    """Export archive or selection"""
    try:
        archive = Archive(Path(archive_path))
        archive.load()
        
        export_service = ExportService(archive)
        
        def progress_callback(current, total, message):
            click.echo(f"Progress: {current}/{total} - {message}")
        
        export_service.set_progress_callback(progress_callback)
        
        output = Path(output_path)
        
        if format == 'bagit':
            result_path = export_service.export_to_bagit(output)
        else:
            # Export all assets to directory
            search_service = SearchService(archive)
            all_assets, _ = search_service.search(limit=10000)
            asset_ids = [asset.asset_id for asset in all_assets]
            result_path = export_service.export_selection(asset_ids, output, format='directory')
        
        click.echo(f"Export completed: {result_path}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('archive_path', type=click.Path(exists=True))
@click.option('--name', '-n', required=True, help='Profile name')
@click.option('--description', '-d', default='', help='Profile description')
def create_profile(archive_path, name, description):
    """Create a new metadata profile"""
    try:
        archive = Archive(Path(archive_path))
        archive.load()
        
        profile_id = name.lower().replace(' ', '_')
        profile = Profile(
            id=profile_id,
            name=name,
            description=description,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )
        
        # Add some common fields
        profile.add_field(MetadataField(
            name="title",
            display_name="Title",
            field_type=FieldType.TEXT,
            required=True
        ))
        
        profile.add_field(MetadataField(
            name="description",
            display_name="Description",
            field_type=FieldType.TEXTAREA
        ))
        
        profile.add_field(MetadataField(
            name="tags",
            display_name="Tags",
            field_type=FieldType.TAGS
        ))
        
        profile_path = archive.profiles_path / f"{profile_id}.json"
        profile.save_to_file(profile_path)
        
        click.echo(f"Created profile '{name}' ({profile_id})")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('archive_path', type=click.Path(exists=True))
def rebuild_index(archive_path):
    """Rebuild the search index"""
    try:
        archive = Archive(Path(archive_path))
        archive.load()
        
        indexing = IndexingService(archive)
        success, errors = indexing.index_all_assets(force_reindex=True)
        
        click.echo(f"Index rebuilt: {success} successful, {errors} errors")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()