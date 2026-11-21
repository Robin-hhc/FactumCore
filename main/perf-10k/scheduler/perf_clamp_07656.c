/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07656(unsigned int count)
{
    const unsigned int limit = 182u;
    return count > limit ? limit : count;
}
