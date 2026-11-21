/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09264(unsigned int count)
{
    const unsigned int limit = 128u;
    return count > limit ? limit : count;
}
