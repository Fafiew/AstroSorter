# AstroSorter - Astrophotography Image Classifier

## Project Overview
- **Project Name**: AstroSorter
- **Type**: Desktop Application (Windows Standalone)
- **Core Functionality**: Automatically classify and sort astrophotography images into calibration types (Lights, Darks, Flats, Biases, Flat-Darks)
- **Target Users**: Amateur and professional astrophotographers

## UI/UX Specification

### Layout Structure
- **Single Window Application** with sidebar navigation
- **Main Content Area**: Displays classification results and file lists
- **Header**: Application title with modern branding
- **Sidebar**: Navigation and quick actions
- **Footer**: Status bar with processing information

### Visual Design

#### Color Palette
- **Primary Background**: #1a1a2e (Deep space blue)
- **Secondary Background**: #16213e (Dark navy)
- **Accent Color**: #0f3460 (Medium blue)
- **Highlight**: #e94560 (Cosmic red)
- **Success**: #00d9ff (Cyan)
- **Warning**: #ffa500 (Orange)
- **Text Primary**: #ffffff (White)
- **Text Secondary**: #a0a0a0 (Gray)

#### Typography
- **Font Family**: Segoe UI, Inter
- **Headings**: 24px bold
- **Body**: 14px regular
- **Small**: 12px

#### Spacing System
- **Base Unit**: 8px
- **Padding**: 16px (2 units)
- **Margins**: 24px (3 units)
- **Border Radius**: 12px for cards, 8px for buttons

#### Visual Effects
- **Card Shadows**: 0 4px 20px rgba(0, 217, 255, 0.1)
- **Hover Effects**: Brightness increase + subtle scale
- **Transitions**: 0.3s ease for all interactive elements
- **Glass Morphism**: Semi-transparent panels with blur

### Components

#### Sidebar Navigation
- Logo/Brand area
- Navigation items: Home, Source Files, Classification, Settings
- Collapse/Expand toggle
- States: default, hover (highlight), active (accent)

#### Drop Zone
- Large dashed border area
- Drag & drop visual feedback
- Icon and text prompt
- States: default, hover (glow), active (processing)

#### Classification Cards
- Image type icon
- File count badge
- Progress indicator during processing
- Expandable file list

#### Results Table
- Sortable columns: Filename, Type, Confidence, Exposure, ISO, Camera
- Row selection with checkbox
- Context menu on right-click
- Alternating row colors

#### Settings Panel
- Grouped settings with labels
- Toggle switches for options
- Dropdown selectors
- File path browsers

#### Progress Indicators
- Circular progress for overall
- Linear progress bars for individual files
- Animated processing indicator

## Functionality Specification

### Core Features

#### 1. File Input
- Drag & drop folder/files
- Browse button for folder selection
- Recursive folder scanning
- Supported formats:
  - **RAW**: .CR2 (Canon), .CR3, .NEF (Nikon), .ARW (Sony), .RAF (Fuji), .DNG (Adobe), .ORF (Olympus), .RW2 (Panasonic)
  - **FITS**: .fit, .fits
  - **TIFF**: .tif, .tiff
  - **JPEG**: .jpg, .jpeg

#### 2. Image Classification Engine
- **Primary Method**: Metadata analysis
  - Read FITS headers (IMAGETYP, EXPTIME, FILTER, CCD-TEMP, etc.)
  - Read EXIF data from RAW files (ExposureTime, ISOSpeedRatings, etc.)
  - Read filename patterns

- **Classification Rules**:
  - **BIAS**: Exposure time ≤ 0.01s or explicit IMAGETYP=BIAS
  - **FLAT**: Exposure time 0.01-10s, has FILTER, low mean brightness
  - **DARK**: Exposure time > 10s, no object/filter, matches dark temp
  - **LIGHT**: Exposure time > 10s, has object name
  - **FLAT-DARK**: Dark frames for flat calibration

- **Secondary Method**: Image statistics (when metadata insufficient)
  - Mean ADU value analysis
  - Standard deviation analysis
  - Hot pixel detection
  - Histogram shape analysis

#### 3. Sorting & Export
- Create sorted folders in output directory
- Copy or move files (user choice)
- Preserve original file metadata
- Generate classification report (CSV/JSON)
- Undo support

#### 4. Preview & Validation
- Thumbnail preview of selected images
- Display EXIF/FITS metadata
- Confidence score display
- Manual override capability

### User Interactions
1. Launch app → See welcome screen with drop zone
2. Drop folder → Shows scanning progress
3. Processing → Live classification with progress
4. Results → Review and manually adjust if needed
5. Export → Choose destination and sorting method
6. Complete → Show summary and open folder option

### Edge Cases
- Empty folders
- Corrupted files (skip with warning)
- Mixed file types in folder
- Duplicate filenames
- Read-only destination
- Very large datasets (batch processing)

## Acceptance Criteria

### Visual Checkpoints
- [ ] Dark theme with cosmic aesthetic loads correctly
- [ ] Sidebar navigation is functional and styled
- [ ] Drop zone has proper visual feedback
- [ ] Classification cards show correct counts
- [ ] Progress indicators animate smoothly
- [ ] All text is readable with proper contrast

### Functional Checkpoints
- [ ] Can drag and drop folders
- [ ] Can browse and select folders
- [ ] Correctly identifies FITS files by header
- [ ] Correctly identifies RAW files by EXIF
- [ ] Handles mixed file types
- [ ] Creates proper output folders
- [ ] Export works with copy and move
- [ ] Manual override changes classification
- [ ] Settings persist between sessions
- [ ] Error handling shows user-friendly messages

### Performance
- [ ] Handles 1000+ files without freezing
- [ ] Progress updates in real-time
- [ ] Responsive UI during processing
