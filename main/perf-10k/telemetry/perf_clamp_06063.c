/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06063(unsigned int count)
{
    const unsigned int limit = 242u;
    return count > limit ? limit : count;
}
