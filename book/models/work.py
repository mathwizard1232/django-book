from django.db import models
from book.models.author import Author
import logging
import re

logger = logging.getLogger(__name__)

class Work(models.Model):
    """
    Core intellectual content created by author(s), independent of format.
    
    For a popular book like Dune which has been printed in many editions and ISBNs,
    there will be a single Work object. This is similar to the previous Book model
    but with expanded capabilities for multiple authors and component works.
    """
    id = models.BigAutoField(primary_key=True)
    
    # Core metadata
    title = models.CharField(max_length=100)
    authors = models.ManyToManyField(Author)
    editors = models.ManyToManyField(Author, related_name='edited_works')
    original_publication_date = models.DateField(null=True, blank=True)
    
    # Work type and relationships
    TYPE_CHOICES = [
        ('NOVEL', 'Novel'),
        ('POEM', 'Poem'),
        ('JOURNALISM', 'Journalism'),
        ('SHORT_STORY', 'Short Story'),
        ('COLLECTION', 'Anthology/Collection'),
    ]
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    # Multi-volume support
    is_multivolume = models.BooleanField(default=False, 
        help_text="Indicates if this Work is a multi-volume set")
    volume_number = models.IntegerField(null=True, blank=True,
        help_text="Optional volume number within a multi-volume set")
    volume_title = models.CharField(max_length=100, blank=True, null=True,
        help_text="Optional specific title for this volume")
    
    # Existing component works relationship
    component_works = models.ManyToManyField('self',
                                           symmetrical=False,
                                           blank=True,
                                           related_name='contained_in')
    
    # Search and external data
    search_name = models.CharField(max_length=100, blank=True, null=True)
    olid = models.CharField(max_length=100)
    
    class Meta:
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['olid']),
            models.Index(fields=['is_multivolume', 'volume_number']),
        ]
    
    def __str__(self):
        base = f"{self.title} by {', '.join(str(author) for author in self.authors.all())}"
        if self.volume_number:
            return f"{base} (Volume {self.volume_number})"
        return base

    @classmethod
    def create_volume_set(cls, title: str, authors=None, editors=None, volume_count: int = 1, **kwargs) -> tuple['Work', list['Work']]:
        """
        Creates a multi-volume Work set with the specified number of volumes.
        
        Args:
            title: The title of the complete set
            authors: Author or list of authors (optional)
            editors: Author or list of editors (optional)
            volume_count: Number of volumes in the complete set
            **kwargs: Additional Work fields (type, original_publication_date, etc.)
        
        Returns:
            Tuple of (parent_work, list_of_volume_works)
        """
        # Create parent Work
        parent_work = cls.objects.create(
            title=title,
            is_multivolume=True,
            **kwargs
        )
        
        # Add authors if present
        if authors:
            if not isinstance(authors, (list, tuple)):
                authors = [authors]
            parent_work.authors.set(authors)
        
        # Add editors if present
        if editors:
            if not isinstance(editors, (list, tuple)):
                editors = [editors]
            parent_work.editors.set(editors)
        
        # Create individual volumes
        volume_works = []
        for vol_num in range(1, volume_count + 1):
            volume = cls.objects.create(
                title=f"{title}, Volume {vol_num}",
                is_multivolume=False,
                volume_number=vol_num,
                type=kwargs.get('type', 'NOVEL'),
                original_publication_date=kwargs.get('original_publication_date')
            )
            if authors:
                volume.authors.set(authors)
            if editors:
                volume.editors.set(editors)
            parent_work.component_works.add(volume)
            volume_works.append(volume)
        
        return parent_work, volume_works

    @classmethod
    def create_partial_volume_set(cls, title: str, volume_numbers: list, authors=None, editors=None, **kwargs):
        """Create a parent work and specified volumes"""
        logger.info("Creating partial volume set with:")
        logger.info("title: %s", title)
        logger.info("volume_numbers: %s", volume_numbers)
        logger.info("kwargs: %s", kwargs)
        
        # Create parent work without authors/editors
        filtered_kwargs = {k:v for k,v in kwargs.items() if k not in ('authors', 'editors')}
        parent_work = cls.objects.create(
            title=title,
            is_multivolume=True,
            **filtered_kwargs
        )
        
        # Set authors and editors after creation
        if authors:
            if not isinstance(authors, (list, tuple)):
                authors = [authors]
            parent_work.authors.set(authors)
        
        if editors:
            if not isinstance(editors, (list, tuple)):
                editors = [editors]
            parent_work.editors.set(editors)

        # Create individual volumes
        volume_works = []
        for volume_number in volume_numbers:
            volume = cls.objects.create(
                title=title,
                is_multivolume=False,
                volume_number=volume_number,
                type=kwargs.get('type', 'NOVEL'),
                original_publication_date=kwargs.get('original_publication_date')
            )
            if authors:
                volume.authors.set(authors)
            if editors:
                volume.editors.set(editors)
            volume_works.append(volume)
        
        return parent_work, volume_works

    @classmethod
    def create_single_volume(cls, set_title: str, volume_number: int, authors, **kwargs):
        logger.info("Creating single volume with:")
        logger.info("set_title: %s", set_title)
        logger.info("volume_number: %s", volume_number)
        logger.info("kwargs: %s", kwargs)
        
        # Try to find existing set
        parent_work = cls.objects.filter(
            title=set_title,
            is_multivolume=True,
            volume_number__isnull=True
        ).first()
        
        if parent_work:
            logger.info("Found existing parent work: %s (ID: %s)", parent_work.title, parent_work.id)
        else:
            logger.info("Creating new parent work")
        
        # Create parent if it doesn't exist
        if not parent_work:
            parent_work = cls.objects.create(
                title=set_title,
                is_multivolume=True,
                volume_number=None,  # Explicitly set to None
                **{k:v for k,v in kwargs.items() if k != 'volume_number'}  # Remove volume_number from kwargs
            )
            if not isinstance(authors, (list, tuple)):
                authors = [authors]
            parent_work.authors.set(authors)
        
        # Create the single volume
        volume = cls.objects.create(
            title=set_title,  # Base title only, volume number handled by __str__
            is_multivolume=False,
            volume_number=volume_number,
            type=kwargs.get('type', 'NOVEL'),
            original_publication_date=kwargs.get('original_publication_date')
        )
        volume.authors.set(authors)
        parent_work.component_works.add(volume)
        
        return parent_work, volume

    @classmethod
    def strip_volume_number(cls, title: str) -> str:
        """Remove volume number from title if present"""
        # Match ", Volume X" or "Volume X" at the end of the string
        volume_pattern = r',?\s*Volume\s+\d+\s*$'
        return re.sub(volume_pattern, '', title).strip()

"""
# Create a complete 5-volume set
parent, volumes = Work.create_volume_set(
    title="The Collected Short Stories of Louis L'Amour",
    authors=author,
    volume_count=5,
    type='COLLECTION'
)

# Create just volume 5
parent, volume5 = Work.create_single_volume(
    set_title="The Collected Short Stories of Louis L'Amour",
    volume_number=5,
    authors=author,
    type='COLLECTION'
)

# Create volumes 1, 3, and 5
parent, volumes = Work.create_partial_volume_set(
    title="The Collected Short Stories of Louis L'Amour",
    authors=author,
    volume_numbers=[1, 3, 5],
    type='COLLECTION'
)
"""