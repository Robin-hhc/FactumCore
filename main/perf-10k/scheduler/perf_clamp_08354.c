/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08354(unsigned int count)
{
    const unsigned int limit = 96u;
    return count > limit ? limit : count;
}
