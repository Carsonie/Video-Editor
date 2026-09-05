package z_slog

// Common Icons and Emojis for Logging

// ANSI Color Codes
const (
	ColorReset         = "\033[0m"
	ColorRed           = "\033[31m"
	ColorGreen         = "\033[32m"
	ColorYellow        = "\033[33m"
	ColorBlue          = "\033[34m"
	ColorMagenta       = "\033[35m"
	ColorCyan          = "\033[36m"
	ColorWhite         = "\033[37m"
	ColorBold          = "\033[1m"
	ColorGray          = "\033[90m"
	ColorBrightRed     = "\033[91m"
	ColorBrightGreen   = "\033[92m"
	ColorBrightYellow  = "\033[93m"
	ColorBrightBlue    = "\033[94m"
	ColorBrightMagenta = "\033[95m"
	ColorBrightCyan    = "\033[96m"
	ColorBrightWhite   = "\033[97m"
	ColorOrange        = "\033[38;5;208m"
	ColorPurple        = "\033[38;5;141m"
)

// Status Icons
const (
	IconSuccess   = "✅"
	IconError     = "❌"
	IconWarning   = "⚠️"
	IconInfo      = "ℹ️"
	IconDebug     = "🔍"
	IconQuestion  = "❓"
	IconCheckmark = "✓"
	IconCross     = "✗"
	IconBullet    = "•"
	IconArrowR    = "→"
	IconArrowL    = "←"
	IconArrowUp   = "↑"
	IconArrowDown = "↓"
	IconValues    = "📊"
	IconReturn    = "↩️"
)

// System Icons
const (
	IconServer    = "🖥️"
	IconDatabase  = "💾"
	IconNetwork   = "🌐"
	IconAPI       = "🔌"
	IconCloud     = "☁️"
	IconTerminal  = "⌨️"
	IconConfig    = "⚙️"
	IconSettings  = "🔧"
	IconTools     = "🛠️"
	IconPackage   = "📦"
	IconFile      = "📄"
	IconFolder    = "📁"
	IconDocument  = "📋"
	IconClipboard = "📎"
)

// Action Icons
const (
	IconStart     = "🚀"
	IconStop      = "🛑"
	IconRestart   = "🔄"
	IconRefresh   = "♻️"
	IconPlay      = "▶️"
	IconPause     = "⏸️"
	IconForward   = "⏩"
	IconBackward  = "⏪"
	IconRecord    = "⏺️"
	IconUpload    = "📤"
	IconDownload  = "📥"
	IconSave      = "💾"
	IconDelete    = "🗑️"
	IconEdit      = "✏️"
	IconCopy      = "📋"
	IconCut       = "✂️"
	IconPaste     = "📌"
	IconSearch    = "🔎"
	IconFilter    = "🔽"
	IconSort      = "↕️"
)

// User & Auth Icons
const (
	IconUser      = "👤"
	IconUsers     = "👥"
	IconAdmin     = "👑"
	IconGuest     = "🧑"
	IconVisitor   = "👁️"
	IconAuth      = "🔐"
	IconLogin     = "🔓"
	IconLogout    = "🔒"
	IconPassword  = "🔑"
	IconToken     = "🎟️"
	IconShield    = "🛡️"
	IconLock      = "🔒"
	IconUnlock    = "🔓"
	IconKey       = "🗝️"
	IconFingerprint = "👆"
)

// Media & Video Icons
const (
	IconVideo     = "🎬"
	IconCamera    = "📹"
	IconFilm      = "🎞️"
	IconImage     = "🖼️"
	IconPhoto     = "📷"
	IconAudio     = "🔊"
	IconMusic     = "🎵"
	IconMicrophone = "🎤"
	IconHeadphones = "🎧"
	IconTV        = "📺"
	IconScreen    = "🖥️"
	IconPhone     = "📱"
	IconTablet    = "📱"
)

// Time & Status Icons
const (
	IconClock     = "🕐"
	IconTimer     = "⏱️"
	IconHourglass = "⏳"
	IconCalendar  = "📅"
	IconDate      = "📆"
	IconAlarm     = "⏰"
	IconStopwatch = "⏱️"
	IconSoon      = "🔜"
	IconNew       = "🆕"
	IconUpdated   = "🆙"
	IconHot       = "🔥"
	IconCool      = "❄️"
)

// Data & Analytics Icons
const (
	IconChart     = "📊"
	IconGraph     = "📈"
	IconTrending  = "📉"
	IconReport    = "📋"
	IconStats     = "📊"
	IconMeter     = "📏"
	IconGauge     = "⚡"
	IconPercent   = "💯"
	IconMoney     = "💰"
	IconDollar    = "💵"
	IconCoin      = "🪙"
)

// Communication Icons
const (
	IconMessage   = "💬"
	IconChat      = "💭"
	IconEmail     = "📧"
	IconMail      = "✉️"
	IconInbox     = "📨"
	IconOutbox    = "📤"
	IconBell      = "🔔"
	IconNotify    = "📢"
	IconAnnounce  = "📣"
	IconPhone2    = "☎️"
	IconComment   = "💬"
)

// Location & Navigation Icons
const (
	IconHome      = "🏠"
	IconOffice    = "🏢"
	IconBuilding  = "🏛️"
	IconMap       = "🗺️"
	IconLocation  = "📍"
	IconPin       = "📌"
	IconCompass   = "🧭"
	IconGlobe     = "🌍"
	IconWorld     = "🌎"
	IconFlag      = "🚩"
)

// Development Icons
const (
	IconCode      = "💻"
	IconBug       = "🐛"
	IconTest      = "🧪"
	IconBuild     = "🔨"
	IconDeploy    = "🚢"
	IconGit       = "📝"
	IconBranch    = "🌿"
	IconMerge     = "🔀"
	IconCommit    = "📌"
	IconPR        = "🔃"
	IconIssue     = "🐞"
	IconFeature   = "✨"
	IconFix       = "🔧"
	IconRefactor  = "♻️"
	IconPerf      = "⚡"
	IconDocs      = "📚"
	IconStyle     = "💄"
)

// Misc Icons
const (
	IconStar      = "⭐"
	IconHeart     = "❤️"
	IconFire      = "🔥"
	IconThumbsUp  = "👍"
	IconThumbsDown = "👎"
	IconParty     = "🎉"
	IconCelebrate = "🎊"
	IconGift      = "🎁"
	IconTrophy    = "🏆"
	IconMedal     = "🥇"
	IconTarget    = "🎯"
	IconRocket    = "🚀"
	IconBomb      = "💣"
	IconBattery   = "🔋"
	IconPlug      = "🔌"
	IconLink      = "🔗"
	IconChain     = "⛓️"
	IconGear      = "⚙️"
	IconWrench    = "🔧"
	IconHammer    = "🔨"
	IconMagnet    = "🧲"
)

// Security Icons
const (
	IconVPN       = "🔐"
	IconEncrypt   = "🔒"
	IconDecrypt   = "🔓"
	IconCertificate = "📜"
	IconSSL       = "🔐"
	IconFirewall  = "🧱"
	IconSecurity  = "🛡️"
	IconPrivacy   = "🕵️"
	IconSafe      = "🔐"
)

// Error & Problem Icons
const (
	IconCritical  = "🚨"
	IconFatal     = "💀"
	IconPanic     = "😱"
	IconBroken    = "💔"
	IconBan       = "🚫"
	IconNoEntry   = "⛔"
	IconCaution   = "⚠️"
	IconDanger    = "☢️"
	IconRadiation = "☣️"
	IconExplosion = "💥"
)
