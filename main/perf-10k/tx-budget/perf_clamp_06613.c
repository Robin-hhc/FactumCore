/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06613(unsigned int count)
{
    const unsigned int limit = 130u;
    return count > limit ? limit : count;
}
