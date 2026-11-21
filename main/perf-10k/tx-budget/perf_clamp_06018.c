/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06018(unsigned int count)
{
    const unsigned int limit = 224u;
    return count > limit ? limit : count;
}
