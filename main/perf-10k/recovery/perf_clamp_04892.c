/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04892(unsigned int count)
{
    const unsigned int limit = 255u;
    return count > limit ? limit : count;
}
