" Vim Configuration

" Compatibility
set nocompatible              " Disable Vi compatibility

" General Settings
set number                    " Show line numbers
set relativenumber            " Show relative line numbers
set ruler                     " Show cursor position
set showcmd                   " Show command in bottom bar
set cursorline                " Highlight current line
set wildmenu                  " Visual autocomplete for command menu
set showmatch                 " Highlight matching [{()}]
set laststatus=2              " Always show status line
set encoding=utf-8            " Use UTF-8 encoding
set fileencoding=utf-8        " Use UTF-8 for file encoding

" Indentation
set tabstop=4                 " Number of visual spaces per TAB
set softtabstop=4             " Number of spaces in tab when editing
set shiftwidth=4              " Number of spaces for autoindent
set expandtab                 " Tabs are spaces
set autoindent                " Auto-indent new lines
set smartindent               " Smart indent

" Search
set incsearch                 " Search as characters are entered
set hlsearch                  " Highlight matches
set ignorecase                " Ignore case when searching
set smartcase                 " Override ignorecase if uppercase used

" Performance
set lazyredraw                " Redraw only when needed
set ttyfast                   " Fast terminal connection

" Backup and Swap
set nobackup                  " Don't create backup files
set nowritebackup             " Don't write backup files
set noswapfile                " Don't create swap files

" Undo
set undofile                  " Persistent undo
set undodir=~/.vim/undo       " Undo directory
set undolevels=1000           " Number of undo levels

" Split behavior
set splitbelow                " Horizontal splits below
set splitright                " Vertical splits to the right

" Folding
set foldenable                " Enable folding
set foldlevelstart=10         " Open most folds by default
set foldmethod=indent         " Fold based on indent level

" Mouse support
set mouse=a                   " Enable mouse in all modes

" Clipboard
set clipboard=unnamed         " Use system clipboard

" Color scheme
syntax enable                 " Enable syntax highlighting
set background=dark           " Dark background

" Status line
set statusline=%F%m%r%h%w\ [FORMAT=%{&ff}]\ [TYPE=%Y]\ [POS=%l,%v][%p%%]\ %{strftime('%d/%m/%y\ -\ %H:%M')}

" Key mappings
let mapleader=","             " Leader key

" Quick save
nnoremap <leader>w :w<CR>

" Quick quit
nnoremap <leader>q :q<CR>

" Turn off search highlight
nnoremap <leader><space> :nohlsearch<CR>

" Move vertically by visual line
nnoremap j gj
nnoremap k gk

" Split navigation
nnoremap <C-h> <C-w>h
nnoremap <C-j> <C-w>j
nnoremap <C-k> <C-w>k
nnoremap <C-l> <C-w>l

" Buffer navigation
nnoremap <leader>n :bnext<CR>
nnoremap <leader>p :bprevious<CR>
nnoremap <leader>d :bdelete<CR>

" Toggle line numbers
nnoremap <leader>ln :set number!<CR>

" Toggle relative line numbers
nnoremap <leader>rn :set relativenumber!<CR>

" Edit vimrc
nnoremap <leader>ev :vsplit $MYVIMRC<CR>

" Reload vimrc
nnoremap <leader>sv :source $MYVIMRC<CR>

" File type specific settings
autocmd FileType python setlocal tabstop=4 shiftwidth=4 expandtab
autocmd FileType javascript setlocal tabstop=2 shiftwidth=2 expandtab
autocmd FileType typescript setlocal tabstop=2 shiftwidth=2 expandtab
autocmd FileType yaml setlocal tabstop=2 shiftwidth=2 expandtab
autocmd FileType go setlocal tabstop=4 shiftwidth=4 noexpandtab

" Auto-create undo directory
if !isdirectory($HOME."/.vim/undo")
    call mkdir($HOME."/.vim/undo", "p", 0700)
endif

" Trim trailing whitespace on save
autocmd BufWritePre * :%s/\s\+$//e

" Return to last edit position when opening files
autocmd BufReadPost *
     \ if line("'\"") > 0 && line("'\"") <= line("$") |
     \   exe "normal! g`\"" |
     \ endif
