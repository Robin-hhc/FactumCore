/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06889(unsigned int count)
{
    const unsigned int limit = 91u;
    return count > limit ? limit : count;
}
