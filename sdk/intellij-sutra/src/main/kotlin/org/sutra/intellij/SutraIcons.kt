package org.sutra.intellij

import com.intellij.openapi.util.IconLoader

/**
 * Centralized icon loader. Keep the lookup path stable — every reference to
 * the Sutra file icon flows through here so re-theming is a single-file edit.
 */
object SutraIcons {
    @JvmField
    val FILE = IconLoader.getIcon("/icons/sutra.svg", SutraIcons::class.java)
}
